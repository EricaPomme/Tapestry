# Tapestry Backup Automation Tool
# Coded in python3 at Patch Savage Labs
# git: ~/ZAdamMac/Patchs-Tapestry
global version; version = 'DevBuild'  # Sets the version to display. "DevBuild" enables some extra debugging not normally accessable

# Importing Modules
import argparse
import configparser
import datetime
from datetime import date
import gnupg
import math
import multiprocessing as mp
import os
import os.path
import pickle
import platform
import shutil
import tarfile

# Defining Classes
class skipLogger:  # dedicated skip-logging handler for use in buildBlocks
    def __init__(self, landingdir,name):  # starts the skiplogger and tells it it will be writing to landingdir with name
        landingAbs = os.path.join(landingdir, name)
        if not os.path.exists(landingdir):
            os.makedirs(landingdir)
        self.loggerfile = open(landingAbs, "w")  # This will REPLACE the existing logfile with the new one so BE FUCKING CAREFUL
        self.loggerfile.write("The files in the following locations were excluded from the most recent backup. \n")
        self.loggerfile.write("This was due to their filesize exceeding the configured blocksize limit. \n")
        self.loggerfile.write("\n")

    def log(self, foo):  # Formats foo nicely and adds it to the log
        self.loggerfile.write(foo + '\n')

    def save(self):  # saves the file to disk. Once used you have to re-instance the logger
        self.loggerfile.write("\n")
        self.loggerfile.write("\n This backup was run on " + str(date.today()))
        self.loggerfile.flush()
        self.loggerfile.close()


class tapBlock(object):
    def __init__(self, size, label, index):
        self.sizeCur = 0
        self.sizeMax = size
        self.label = label
        self.full = False
        self.contents = {}
        self.index = index #This is the index number used to find the right lock for later

    def add(self, FID, fSize, fPath):  # General function for adding a file to the box. Called during block assembly.
        if (self.sizeMax - self.sizeCur) < smallest:
            self.full = True
            return "full"
        if fSize > (self.sizeMax - self.sizeCur):  # Handling for files larger than will fit in the current block
            return "pass"
        if fSize <= (self.sizeMax - self.sizeCur):  # This file fits
            self.contents.update({FID: fPath})
            self.sizeCur += fSize
            return "stored"

    def pack(self):  # enques the contents of the block for packaging
        os.chdir(ns.drop)
        global tasks
        for file in self.contents:
            tasks.put(buildTasker(self.label, file, self.contents[file], self.index))


class tapProc(mp.Process):
    def __init__(self, qTask):
        mp.Process.__init__(self)
        self.qTask = qTask
        os.chdir(ns.workDir)

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.qTask.get()
            if next_task is None:
                debugPrint('%s: Exiting' % proc_name)
                self.qTask.task_done()
                break
            next_task()
            self.qTask.task_done()
        return


class buildTasker(object):
    def __init__(self, tarf, FID, PATH, index):
        self.tarf = tarf
        self.a = FID
        self.b = PATH
        self.index = index #index number of the appropriate mutex

    def __call__(self):
        os.chdir(ns.workDir)
        if os.path.exists(self.tarf): #we need to know if we're starting a new file or not.
            fLock = locks[self.index] #Aquires the lock indicated in the index value from the master
            fLock.acquire()
            tar = tarfile.open(name=self.tarf, mode="a:")
            tar.add(self.b, arcname=self.a, recursive=False)
            tar.close()
            fLock.release()

class encTasker(object):
    def __init__(self, t, fp):
        self.tarf = t
        self.fp = fp

    def __call__(self):
        with open(self.tarf, "r") as p:
            os.chdir(ns.workDir)
            tstring = self.tarf
            tapped = self.tarf.replace(".tar", ".tap")
            tgtOutput = os.path.join(ns.drop, tapped)
            debugPrint("Encrypting - sending block to: " + tgtOutput)
            with open(tstring, "rb") as tgt:
                k = gpg.encrypt_file(tgt, self.fp, output=tgtOutput, armor=True, always_trust=True)
            if k.ok:
                debugPrint("Encryption Success.")
            elif not k.ok:
                debugPrint(str(k.status)) #Displays the specific encryption error encountered if encryption fails


class sigTasker(object):
    def __init__(self, block, sigfp):
        self.block = block
        self.fp = sigfp

    def __call__(self):
        os.chdir(ns.drop)
        with open(self.block, "rb") as p:
            tgtOutput = self.block + ".sig"
            debugPrint("Signing: " + tgtOutput)
            sis = gpg.sign_file(p, keyid=self.fp, output=tgtOutput, detach=True)


class recTask(object):
    def __init__(self, tar, fid, catdir, pathend):
        self.tar = tar
        self.fid = fid
        self.catdir = catdir
        self.pathend = pathend

    def __call__(self):
        absTar = os.path.join(ns.workDir, self.tar)
        pathEnd = self.pathend.strip('~/')
        absFile = os.path.join(self.catdir,pathEnd)
        placement, nameProper = os.path.split(absFile)  # split the pathend component into the subpath from the category dir, and the original filename.
        with tarfile.open(absTar, "r") as tf:
            tf.extract(self.fid, path=placement)  # the file is now located where it needs to be.
        placed = os.path.join(placement, self.fid)
        os.rename(placed, absFile)  # and now it's named correctly.
        debugPrint("Placed " + str(pathEnd))

class recProc(mp.Process):
    def __init__(self, qTask):
        mp.Process.__init__(self)
        self.qTask = qTask
        os.chdir(ns.drop)

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.qTask.get()
            if next_task is None:
                # Poison pill means shutdown
                debugPrint('%s: Exiting' % proc_name)
                self.qTask.task_done()
                break
            next_task()
            self.qTask.task_done()
        return


# Defining all functions!
def debugPrint(foo):
    if ns.debug:
        print(str(foo))


def announce():
    if __name__ == '__main__':
        print("Welcome to Tapestry Backup Tool Version " + version)
    if platform.system() == "Windows":
        print("Unfortunately, windows functionality is currently blocked for incompletion.")
        print("Please watch the repo for news and updates about this feature.")
        exit()

def init():
    print("Configuration file not found.")
    print("Beginning first-time setup.")
    print("To begin with, please provide your username on this system.")
    uid = input("Username:")
    config.set("Environment Variables", "uid", str(uid))
    print("Next, enter a label to uniquely identify this computer.")
    compID = input("CompID:")
    config.set("Environment Variables", "compID", str(compID))
    print("Please enter the desired blocksize in MB.")
    blockSize = input("(4000)")
    config.set("Environment Variables", "compID", blockSize)
    print("If you have a signing key you wish to use, please enter it, else 0.")
    sigFP = input("FP: ")
    config.set("Environment Variables", "signing fp", str(sigFP))
    if sigFP != "0":
        config.set("Environment Variables", "sign by default", str(True))
    else:
        config.set("Environment Variables", "sign by default", str(False))
    print("Excellent. Tapestry will now create a default configuration file here:")
    print(str(os.getcwd()))
    config.set("Default Locations/Nix", "Docs", "/home/" + uid + "/Documents")
    config.set("Default Locations/Nix", "Photos", "/home/" + uid + "/Pictures")
    config.set("Additional Locations/Nix", "Video", "/home/" + uid + "/Videos")
    config.set("Additional Locations/Nix", "Music", "/home/" + uid + "/Music")
    config.set("Default Locations/Win", "Docs", "C:/Users/" + uid + "/My Documents")
    config.set("Default Locations/Win", "Photos", "C:/Users/" + uid + "/My Pictures")
    config.set("Additional Locations/Win", "Video", "C:/Users/" + uid + "/My Videos")
    config.set("Additional Locations/Win", "Music", "C:/Users/" + uid + "/My Music")
    print("Please review this file. If you need to make any changes to the included backup")
    print("locations, please run the program again with the flag --setup.")
    with open("tapestry.cfg", "w") as cfg:
        config.write(cfg)
    exit()


def checkGPGConfig():
    if ns.signing:  # if signing is disabled by default we don't care about loopback pinentry because a DR key doesn't use a passphrase
        tgt = ns.gpgDir + "/gpg-agent.conf"
        configured = False
        with open(tgt, "rw") as conf:
            for line in conf:
                if "allow-loopback-pinentry" in line:
                    configured = True
                    break
        if not configured:
            print("Tapestry has detected that loopback pintentry is disabled in your gpg installation.")
            print("Tapestry can enable this function, but doing so carries security risks. See the readme.")
            print("Press enter to accept these risks, or control-c to cancel.")
            conf.write("allow-loopback-pinentry")
            conf.close()
        else:
            conf.close()

def setup():
    global setupMode
    setupMode = True
    print("Entering the setup menu")
    while setupMode:
        print("Please Select from the following options:")
        print("1. Change User ID")
        print("2. Change Machine Label")
        print("3. Change Block Size")
        print("4. Directory Management")
        print("5. Key Options")
        print("6. Quit")
        func = input("Option:")
        if func == "1":
            print("Please enter the desired username.")
            uid = input("Username:")
            config.set("Environment Variables", "uid", str(uid))
            print("New UID Set: " + uid)
        elif func == "2":
            print("The current machine label is: " + str(config.get("environment Variables", "compID")))
            print("Please enter the new label.")
            compID = input("Machine Label:")
            config.set("Environment Variables", "compID", str(compID))
            print("The new label was set to :" + compID)
        elif func == "3":
            print("The Blocksize determines the maximum size in MB a .tap block can be.")
            print("It is recommended to choose a value 100 MB less than the capacity of your media.")
            print("Please enter a new blocksize in MB.")
            newSize = input("Default is 4000:")
            config.set("Environment Variables", "blockSize", newSize)
        elif func == "4":
            print("The directory management function is under construction.")
            print("Your configuration file is at:")
            locationConfig = os.path.join(ns.homeDir, "tapestry.cfg")
            print(str(locationConfig))
            print("Please edit this file directly to add, remove, or change target directories and their labels.")
        elif func == "5":
            print("Tapestry can sign your blocks for you, to prevent tampering.")
            if ns.signing:
                print("Default signing is currently on.")
            else:
                print("Default signing is currently off.")
            print("Blocks will be signed with the key with the following fingerprint:")
            print(str(ns.sigFP))
            print("You can:")
            print("1. Toggle Default Signing")
            print("2. Assign a new signing key")
            print("3. Toggle Keyring Mode.")
            print("4. Go Back")
            subfunc = input("Choice?")
            if subfunc == "1":
                if ns.signing:
                    ns.signing = False
                    config.set("Environment Variables", "sign by default", str(False))
                else:
                    ns.signing = True
                    config.set("Environment Variables", "sign by default", str(True))
            elif subfunc == "2":
                print("Please enter the fingerprint of the new key.")
                sigFP =input("FP: ")
                config.set("Environment Variables", "signing fp", str(sigFP))
            elif subfunc == "3":
                if not ns.keyringMode:
                    ns.keyringMode = True
                    config.set("Environment Variables", "keyringMode", str(True))
                else:
                    ns.keyringMode = False
                    config.set("Environment Variables", "keryingMode", str(False))
            else:
                pass
        elif func == "6":
            print("Exiting Setup.")
            setupMode = False
            with open("tapestry.cfg", "w") as cfg:
                config.write(cfg)
        else:
            print("Your entry was not a valid option.")
            print("Please enter the number of the option you wish to execute.")

def findKeyFile(arg):
    foundKey = False
    global pathKey
    if not ns.keyringMode:
        if arg == "pub":
            tgt = "DRPub.key"
        elif arg == "sec":
            tgt = "DR.key"
        if ns.currentOS == "Linux":
            dirSearch = ("/media/" + uid)
            for root, dirs, files in os.walk(dirSearch):
                for file in files:
                    if file == tgt:
                        foundKey = True
                        pathKey = os.path.join(root, tgt)
                        debugPrint("Found key at: " + pathKey)
        if ns.currentOS == "Windows":
            drives = ['{}:\\' for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ']
            for drive in drives:
                if os.path.isdir(drive):
                    for root, dirs, files in os.walk(drive):
                        for file in files:
                            if file == tgt:
                                foundKey = True
                                pathKey = os.path.join(root, tgt)
                                debugPrint("Found key at: " + pathKey)
                if foundKey:
                    break
    else:
        print("Tapestry will use the key with the fingerprint %s for this session." % ns.expectedFP)

    if not foundKey:
        if not ns.keyringMode:
            print("No key found, beginning new key generation. Press ctrl+c to cancel.")
            getPassphrase = True
            while getPassphrase:
                print("Please enter a passphrase to protect this recovery key. Leave blank to skip.")
                s1 = input(">")
                if s1 is not None:
                    print("Please enter the passphrase again.")
                    s2 = input(">")
                    if s1 == s2:
                        ns.secret = s1
                        break
                    else:
                        pass
                else:
                    ns.secret = None
                    getPassphrase = False
            print("Generating a new recovery key, please stand by.")
            input_data = gpg.gen_key_input(key_type="RSA", key_length=2048, name_real=str(uid),
                                           name_comment="Disaster Recovery", name_email="nul@autogen.key",
                                           passphrase=ns.secret)
            keypair = gpg.gen_key(input_data)
            debugPrint(keypair.fingerprint)
            fp = keypair.fingerprint  # Changes the value of FP to the new key
            config.set("Environment Variables", "Expected FP", str(fp))  # sets this value in config
            with open(cfg, "w") as cf:
                config.write(cf)
            if not os.path.isdir(ns.drop):
                os.mkdir(ns.drop)
            os.chdir(ns.drop)
            pubOut = gpg.export_keys(fp)
            keyOut = gpg.export_keys(fp, True)
            pubFile = os.open("DRPub.key", os.O_CREAT | os.O_RDWR)
            pubHandle = os.fdopen(pubFile, "w")
            pubHandle.write(str(pubOut))
            pubHandle.close()
            keyFile = os.open("DR.key", os.O_CREAT | os.O_RDWR)
            keyHandle = os.fdopen(keyFile, "w")
            keyHandle.write(str(keyOut))
            keyHandle.close()
            print("The exported keys have been saved in the output folder. Please move them to removable media.")


# noinspection PyGlobalUndefined
def loadKey():
    global activeFP
    debugPrint("loadkey Start")
    if not ns.keyringMode:
        foo = input("Press enter to confirm that the system will use the key located at " + pathKey)
        keyFile = open(pathKey)
        keyData = keyFile.read()
        importResult = gpg.import_keys(keyData)
        debugPrint("I have imported key: " + importResult.fingerprints[0])
        debugPrint("I was expecting: " + ns.expectedFP)
        if str(importResult.fingerprints[0]) != ns.expectedFP:
            print(
                "WARNING: the fingerprint of the DR key imported from the supplied thumb drive does not match the expected value.")
            print("This could pose a threat to the privacy of your backups.")
            print("If this is acceptable, type OK to continue. Your expected FP value will be changed.")
            confirmation = input("OK?")
            if confirmation == "OK":
                debugPrint("Setting the new expected fp to %s" % str(importResult.fingerprints[0]))
                config.set("Environment Variables", "expected fp", str(importResult.fingerprints[0]))
                with open(cfg, "w") as cfile:
                    config.write(cfile)
            else:
                print("You have indicated you do not wish to use the current key. The program will now terminate.")
                rmkey()
                exit()
        debugPrint(str(importResult.count) + " keys imported.")
        print("Key imported. If program terminates irregularly, remove manually from GPG.")
        activeFP = importResult.fingerprints[0]

    if ns.keyringMode:
        debugPrint("Fetching key from Keyring")
        ns.activeFP = ns.expectedFP
        debugPrint(ns.activeFP)


def createDIRS():
    if not os.path.exists(ns.workDir):
        os.mkdir(ns.workDir)
    if not os.path.exists(ns.drop):
        os.mkdir(ns.drop)


# noinspection PyGlobalUndefined
def findblock():  # Time to go grepping for taps!
    os.chdir(ns.media)
    for foo, bar, files in os.walk(ns.media):
        for file in files:
            if file.endswith(".tap"):
                os.chdir(foo)
                global foundBlock;  foundBlock = file


# noinspection PyGlobalUndefined
def validateBlock():
    print("Checking the validity of this disk's signature.")
    global valid
    global sig; sig = None
    for dont, care, files in os.walk(ns.media):
        for file in files:
            debugPrint("Looking for a sig at file: " + file)
            if file.endswith(".sig"):
                sig = os.path.join(dont, file)
            elif file.endswith(".tap"):
                data = os.path.join(dont, file)
            else:
                continue
    if sig is None:
        print("No signature is available for this block. Continue?")
        go = input("y/n?")
        if go.lower() == "y":
            valid = True
        else:
            print("Aborting backup.")
            cleardown()
            exit()
    else:
        with open(sig, "rb") as fsig:
            verified = gpg.verify_file(fsig, data)
        if verified.trust_level is not None and verified.trust_level >= verified.TRUST_FULLY:
            valid = True
            print("This block has been verified by %s, which is sufficiently trusted." % verified.username)
        else:
            print("This block claims to have been signed by %s." % verified.username)
            print("The signature is %s. Continue?" % verified.trust_text)
            go = input("y/n?")
            if go.lower() == "y":
                valid = True
            else:
                print("Aborting backup.")
                cleardown()
                exit()


def decryptBlock():
    global foundBlock
    outputTGT = str(os.path.join(ns.workDir, foundBlock))
    with open(foundBlock, "rb") as kfile:
        baz = gpg.decrypt_file(kfile, output=outputTGT, always_trust=True)
        if not baz.ok:
            debugPrint("Decryption Error: " + str(baz.status))
            print("Tapestry could not decrypt the block. Shutting down.")
            cleardown()
            exit()

# noinspection PyGlobalUndefined,PyGlobalUndefined,PyGlobalUndefined
def openPickle():
    for foo, bar, files in os.walk(ns.workDir):
        for file in files:
            if file.endswith(".tap"):
                with tarfile.open(os.path.join(foo, file), "r") as tfile:
                    tfile.extract("recovery-pkl", path=ns.workDir)
    for a, b, files in os.walk(ns.workDir):
        for file in files:
            if file == "recovery-pkl":
                foo = os.path.join(a, file)
                global recPaths
                global recSections
                global numBlocks
                with open(foo, "rb") as baz:
                    listRecovery = pickle.load(baz)
                numBlocks, recPaths, recSections = listRecovery
    if len(
            recPaths) > 0:  # Throws an internal error if the required files are not properly mounted and closes the program so that it will not damage the archive
        print("Found Recovery Table 1")
    else:
        print(
            "There was a problem finding the file 'recPaths' on the disk. Please reload this program and try again, being careful to use Disk 1.")
        cleardown()  # Deletes temporary files to prevent system bloat
        rmkey()  # removes the recovery secret key from the keyring per protocol
        exit()
    if len(recSections) > 0:
        print("Found Recovery Table 2")
    else:
        print(
            "There was a problem finding the file 'recovery.pkl' on the disk. Please reload this program and try again, being careful to use Disk 1.")
        cleardown()
        rmkey()
        exit()


# noinspection PyGlobalUndefined
def unpackBlocks():
    if __name__ == '__main__':
        global tasker
        tasker = mp.JoinableQueue()
        for foo, bar, files in os.walk(ns.workDir):
            for file in files:
                if file.endswith(".tap"):
                    with tarfile.open(os.path.join(foo, file), "r")as tf:
                        for item in tf.getnames():  # at this point item yields a tap FID
                            if item == "recovery-pkl": #avoids a keyerror later.
                                continue
                            cat = recSections[item]
                            try:
                                catdir = dirActual[cat]
                            except KeyError:
                                catdir = os.path.join(ns.drop, cat)
                            pathend = recPaths[item]
                            tasker.put(recTask(file, item, catdir, pathend))
        global workers; workers = []
        for i in range(ns.numConsumers):
            workers.append(recProc(tasker))
        for w in workers:
            w.start()
        tasker.join()
        for foo in range(ns.numConsumers):
            tasker.put(None)  # seed poison pills at the end of the queue to kill the damn consumers
        tasker.join()

def rmkey():
    if not ns.keyringMode:
        gpg.delete_keys(ns.activeFP, True)
        gpg.delete_keys(ns.activeFP)
        print("The recovery key has been deleted from the keyring.")


def cleardown():
    if os.path.exists(ns.workDir):
        shutil.rmtree(ns.workDir)
    rmkey()


# noinspection PyGlobalUndefined,PyGlobalUndefined,PyGlobalUndefined
def getContents(category, tgt):
    print("Currently walking the " + category + " directory.")
    for fromRoot, dirs, files, in os.walk(str(tgt)):
        for item in files:
            global sumSize
            global counterFID
            global listSection
            foo = counterFID + 1
            counterFID = foo
            metaTGT = os.path.join(fromRoot, item)
            size = os.path.getsize(metaTGT)
            fooSize = sumSize + size
            sumSize = fooSize
            listAbsolutePaths.update({str(counterFID): str(metaTGT)})
            listFSNames.update({str(counterFID): str(item)})
            listSizes.update({str(counterFID): str(size)})
            relativePath = metaTGT.replace(tgt, "~",
                                           1)  # removes tgt from the path string, leaving the path string after the root of TGT, including subfolders, for recovery.
            listRelativePaths.update({str(counterFID): str(relativePath)})
            listSection.update({str(counterFID): str(category)})
    debugPrint("After crawling " + category + " there are " + str(len(listAbsolutePaths)) + " items in the index.")


# noinspection PyGlobalUndefined,PyGlobalUndefined
def makeIndex():  # does some operations to the working dictionaries to remove items that are too large and place them in order.
    print("Compiling the working indexes")
    global workIndex
    workIndex = sorted(listSizes, key=listSizes.__getitem__)
    workIndex.reverse()  # yields the index sorted by descending file size.
    for item in workIndex:  # We need to remove the largest items.
        size = int(listSizes[item])
        if size > blockSizeActual:
            print("Error: %s is too large to be processed and will be excluded." % listFSNames[item])
            skiplogger.log(listAbsolutePaths[item])
            del workIndex[int(item)]
    global smallest
    smallest = int(listSizes[workIndex[(len(workIndex)-1)]])


def buildBlocks():
    global blocks
    blocks = []
    print("Beginning the blockbuilding process. This may take a moment.")
    numBlocks = math.ceil(sumSize / blockSizeActual)
    debugPrint("numblocks = "+ str(numBlocks))
    for i in range(int(numBlocks)):
        SID = str(str(compid) +"-"+ str(date.today())+"-"+ str(i+1) + ".tar")
        blocks.append(tapBlock(blockSizeActual, SID, i))
    for block in blocks:
        debugPrint("Testing in Block: " + str(block))
        activeIndex = workIndex.copy() #At the start of each block we clone the whole index for it to track over.
        if not block.full:
            for FID in activeIndex:
                pos = workIndex.index(FID)
                fSize = listSizes[FID]
                status = block.add(FID, int(fSize), listAbsolutePaths[FID])
                if status == "pass":
                    pass
                elif status == "stored":
                    del workIndex[pos] #placed items are removed from the work index
        if len(workIndex) == 0:
            break
    print("There are no items left to sort.")
    placePickle()

def placePickle():  # generates the recovery pickle and leaves it where it can be found later.
    if __name__ == "__main__":
        os.chdir(ns.workDir)
        global sumBlocks
        sumBlocks = len(blocks)
        listRecovery = [sumBlocks, listRelativePaths,
                        listSection]  # Believe it or not, this number and these two lists are all we need to recover from a tapestry backup!
        recPickle = os.open("recovery.pkl", os.O_CREAT | os.O_RDWR)
        filePickles = os.fdopen(recPickle, "wb")
        pickle.dump(listRecovery, filePickles)
        filePickles.close()
        pathPickle = os.path.join(ns.workDir, "recovery.pkl")
        for block in blocks:
            tar = tarfile.open(block.label, "w:") #attempting workaround to append issue.
            tar.add(pathPickle, arcname="recovery-pkl", recursive=False)
            tar.close()

def processBlocks():  # signblocks is in here now
    print("Packaging Blocks.")
    debugPrint("Spawning %s processes." % ns.numConsumers)
    if __name__ == '__main__':
        global blocks
        os.chdir(ns.workDir)
        global tasks
        tasks = mp.JoinableQueue()
        consumers = []
        global locks
        locks = []
        for i in range(ns.numConsumers):
            consumers.append(tapProc(tasks))
        for b in blocks:
            b.pack()
            locks.append(master.Lock())
        debugPrint("Packed Blocks")
        for w in consumers:
            w.start()
        tasks.join()

        for foo, bar, files in os.walk(ns.workDir):
            for file in files:
                if file.endswith(".tar"):
                    tasks.put(encTasker(file, ns.activeFP))
                    debugPrint("Encryption enqueued")
        tasks.join()
        if ns.signing:
            for foo, bar, taps in os.walk(ns.drop):
                for tap in taps:
                    if tap.endswith(".tap"):
                        tasks.put(sigTasker(tap, ns.sigFP))
        for w in consumers: #Finally, poison pill the worker processes to terminate them.
            tasks.put(None)
        tasks.join()
        debugPrint("End of processBlocks()")


def buildMaster():  # summons the master process and builds its corresponding namespace, then assigns some starting values
    if __name__ == "__main__":
        global master
        master = mp.Manager()
        global ns
        ns = master.Namespace()

        ns.currentOS = platform.system()  # replaces old global var currentOS
        ns.date = datetime.date
        ns.home = os.getcwd()
        ns.numConsumers = os.cpu_count()  # The practical limit of consumer processes during multiprocessed blocks.
        #ns.numConsumers = 1 # existed purely for debugging purposes.
        ns.secret = None  # Placeholder so that we can use this value later as needed. Needs to explicitly be none in case no password is used.

def parseArgs():  # mounts argparser, crawls it and then assigns to the managed namespace
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Automatically backup or restore personal files from the system.")
        parser.add_argument('--rcv', help="Recover a previous archive from disk.", action="store_true")
        parser.add_argument('--setup', help="Loads the program in user configuration mode", action="store_true")
        parser.add_argument('--inc', help="Tells the system to include non-default sections in the backup process.",
                            action="store_true")
        parser.add_argument('--debug', help="Increase output verbosity.", action="store_true")
        args = parser.parse_args()

        ns.rcv = args.rcv
        ns.setup = args.setup
        ns.inc = args.inc
        ns.debug = args.debug

def parseConfig():  # mounts the configparser instance, grabs the config file, and passes its values into the namespace
    if __name__ == "__main__":
        global config
        config = configparser.ConfigParser()
        global cfg
        if version == "DevBuild":
            cfg = "tapestry-test.cfg"
        else:
            cfg = "tapestry.cfg"

        if os.path.exists(os.getcwd() + "/" + cfg):
            config.read(cfg)
            global uninit
            uninit = False
        else:  # the finished version should include a tapestry.cfg file by default for clarity, but in a pinch we can assign some defaults.
            uninit = True
            config.add_section("Environment Variables")
            config.add_section("Default Locations/Nix")
            config.add_section("Additional Locations/Nix")
            config.add_section("Default Locations/Win")
            config.add_section("Additional Locations/Win")
            config.set("Environment Variables", "blockSize", "4000")
            config.set("Environment Variables", "expected fp", "0")
            config.set("Environment Variables", "compid", "uninit")
            config.set("Environment Variables", "keyringMode", str(False))
            config.set("Environment Variables", "sign by default", str(True))
            config.set("Environment Variables", "signing fp", "0")
            config.set("Envrionment Variables", "Drive Letter", "D:/")
            config.set("Environment Variables", "uid",
                       "uninit")  # as a portable function this should work in both Linux and Windows
            if platform.system() == "Linux":  # Some defaults could be better
                uname = os.uname()
                config.set("Environment Variables", "compid",
                           str(uname[1]))  # gets the nodeid and sets it as the computer's name.
            configFile = os.open("tapestry.cfg", os.O_CREAT | os.O_RDWR)
            os.close(configFile)
            with open(cfg, "r+") as t:
                config.write(t)

        ns.expectedFP = config.get("Environment Variables", "Expected FP")
        ns.fp = config.get("Environment Variables", "Expected FP")  # Can be changed during the finding process.
        ns.keyringMode = config.getboolean("Environment Variables", "keyringMode")
        ns.signing = config.getboolean("Environment Variables", "Sign by Default")
        ns.sigFP = config.get("Environment Variables", "Signing FP")

        # We also declare some globals here. They aren't used in the children so they aren't part of ns, but they still need to be declared and still come from config.
        global blockSizeActual
        blockSizeActual = config.getint("Environment Variables", "blockSize") * (
        2 ** 20)  # cfg asks the user for MB, but for actual processes we need bytes
        global compid; compid = config.get("Environment Variables", "compid")
        global driveletter
        driveletter = config.get("Environment Variables",
                                 "drive letter")  # The windows drive letter of the removable disk mount point. Used for rcv mode.
        global uid
        uid = config.get("Environment Variables", "uid")  # Not sure actually used anywhere!

    if ns.currentOS == "Linux":
        ns.workDir = "/tmp/Tapestry/"
        ns.desktop = str("/home/" + uid + "/Desktop")
        ns.gpgDir = str("/home/" + uid + "/.gnupg")
        ns.media = "/media/"
    elif ns.currentOS == "Windows":
        ns.workDir = "C:/Windows/Temp"
        ns.desktop = str("C:/Users/" + uid + "/Desktop")
        ns.gpgDir = "C:/Program Files (x86)/GNU/GnuPG"
        ns.media = driveletter
    ns.drop = ns.desktop + "/Tapestry Outputs/"


def startLogger():
    global skiplogger
    skiplogger = skipLogger(ns.drop, "Skipped Files")

def startGPG():
    global gpg
    gpg = gnupg.GPG(gnupghome=ns.gpgDir, verbose=ns.debug)

def buildOpsList():
    global listDefaults
    global listAdditionals
    global dirActual

    if ns.currentOS == "Linux":
        listDefaults = dict(config.items("Default Locations/Nix"))
        listAdditionals = dict(config.items("Additional Locations/Nix"))
    if ns.currentOS == "Windows":
        listDefaults = dict(config.items("Default Locations/Win"))
        listAdditionals = dict(config.items("Additional Locations/Win"))

    global listRun

    if ns.inc:
        listRun = listDefaults.copy()
        listRun.update(listAdditionals)
    else:
        listRun = listDefaults

    dirActual = listDefaults.copy()
    dirActual.update(listAdditionals)

    ns.dirActual = dirActual #This last value needs to go to namespace because it is needed by the worker processes too.

#We're gonna need some globals
global counterFID; counterFID = 0
global sumSize; sumSize = 0
global listAbsolutePaths; listAbsolutePaths = {}
global listRelativePaths; listRelativePaths = {}
global listSizes; listSizes = {}
global listFSNames; listFSNames = {}
global listSection; listSection = {}

# Runtime
if __name__ == "__main__":
    announce()
    buildMaster()
    parseArgs()
    parseConfig()
    startLogger()
    startGPG()
    if uninit:
        init()
        checkGPGConfig()
        exit()
    elif ns.setup:
        setup()
        exit()
    elif ns.rcv:
        print("Tapestry is ready to recover your files. Please insert the first disk.")
        input("Press any key to continue")
        findKeyFile("sec")
        loadKey()
        buildOpsList()
        createDIRS()
        findblock()
        validateBlock()
        decryptBlock()
        openPickle()
        print("This backup exists in %d blocks." % numBlocks)
        for i in range(numBlocks - 1):
            input("Please insert the next disk and press enter to continue.")
            findblock()
            validateBlock()
            decryptBlock()
        unpackBlocks()
        print("Any files with uncertain placement were moved to the output folder.")
        print("All blocks have now been unpacked. Tapestery will clean up and exit.")
        cleardown()
        exit()
    else:
        createDIRS()
        buildOpsList()
        print("Tapestry is configuring itself. Please wait.")
        findKeyFile("pub")
        loadKey()
        print("Confirm this session will use the following key:")
        print(str(ns.activeFP))
        print("The expected FP is:")
        print(str(ns.activeFP))
        qContinue = input("Continue? y/n>")
        if qContinue.lower() != "y":
            cleardown()
            exit()
        print("Tapestry is preparing the backup index. This may take a few moments.")
        for category in listRun:
            getContents(category, listRun[category])
        makeIndex()
        buildBlocks()
        processBlocks()
        print("The processing has completed. Your .tap files are here:")
        print(str(ns.drop))
        print("Please archive these expediently.")
        cleardown()
        exit()