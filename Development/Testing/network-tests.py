#  Functional Testing Script for Tapestry versions 1.0 and later
#  For full commentary and documentation view TESTDOCS.md in the repo.

#  Import Modules
import configparser as cp
from datetime import date
from ..Testing import framework
from ..Source import dev
import gnupg
import hashlib
import os
import shutil
import ssl

#  Stash classes and functions here if necessary.


def runtime():
    #  Parse test config
    permaHome = os.getcwd()

    cfg = cp.ConfigParser()
    cfg.read("tapestry-test.cfg")
    out = cfg.get("Environment Variables", "output path")
    uid = cfg.get("Environment Variables", "uid")
    host = cfg.get("Environment Variables", "compID")
    test_FTP_user = cfg.get("Network Configuration", "username")
    test_FTP_pw = input("Enter password for FTP testing: ")
    logs = os.path.join(permaHome, "Logs")
    blockSize = cfg.get("Environment Variables", "blocksize")

    # We create a backup of the config to restore to after testing.
    shutil.copy("tapestry-test.cfg", "tapestry-test.cfg.bak")

    pathControl = out.replace("Test", "Control")

    if not os.path.isdir((logs)):
        os.mkdir(logs)

    logname = ("network_test-%s-%s.log" % (uid, str(date.today())))
    log = framework.simpleLogger(logs, logname, "network-tests")

    gpg = gnupg.GPG(gnupghome="/home/"+uid+"/.gnupg")

    print("Beginning Networking Tests")
    log.log("\n\n-------------------------[NETWORK CONNECTIVITY TESTS]--------------------------")
    log.log("\nThis log is for a test of a development version of Tapestry, with SHA256 hash:")
    hasher = hashlib.sha256()
    hasher.update(open("dev.py", "rb").read())
    taphash = hasher.hexdigest()
    log.log("\n"+str(taphash)+"\n")
    os.chdir(permaHome)

    # We use popen not to block the test script while the servers are running, but we need to close them later, so we catch the processes in some vars.
    instFTP = None

    #Test the Bad Link First
    testcontext = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    testcontext.load_verify_locations(cafile="testcert.pem")

    try:
        instFTP = dev.connectFTP("localhost", 201, testcontext, test_FTP_user, test_FTP_pw)
        print("Malicious Connection Test - FAIL - Connection Accepted.")
        log.log("[FAILED] Tapestry connected to the 'malicious' server and accepted it as a\nlegitimate connection.")
    except ConnectionRefusedError:  # This should hopefully be the right exception but some offline tests are required
        print("Malicious Connection Test - PASS - Connection Refused.")
        log.log("[PASSED] The 'malicious' server was correctly rejected by Tapestry's connection\nestablishment function.")

    #Now the Good Link

    try:
        instFTP = dev.connectFTP("localhost", 211, testcontext, test_FTP_user, test_FTP_pw)
        print("Benign Connection Test - PASS - Connection Accepted.")
        log.log("[PASSED] The 'valid' server was accepted by the connection establishment\nfunction and a valid connection object is being passed to the next test.")
    except ConnectionRefusedError or ssl.SSLError:  # This should hopefully be the right exception but some offline tests are required
        print("Benign Connection Test - FAIL - Connection Refused.")
        log.log("[FAILED] The 'valid' server was rejected by the connection establishment\nfunction and the next test must be skipped.")
    log.log("-------------------------------------------------------------------------------")

    #Transfer Tests
    log.log("\n\n--------------------------[NETWORK PUSH/PULL TEST]-----------------------------")
    if instFTP is None:
        print("Skipping Transfer Tests - No FTP Connection could be Established.")
        log.log("[FAILED] The network transfer tests could not be passed as no connection was\nestablished. Verify that vsftpd is configured correctly on the test machine and\nthat tapestry-test.cfg contains the correct credentials for the FTP test user.")
    else:
        print("Beginning file transfer tests using inert transfer article.")
        dev.sendFile(instFTP, "testblock-2001-01-01.txt")
        countPlaced, listPlaced = dev.grepBlocks("testblock", "2001-01-01", instFTP)
        dev.fetchBlock("testblock-2001-01-01.txt", instFTP, out)
        hashControlFTP = hashlib.md5()
        hashControlFTP.update(open("testblock-2001-01-01.txt", "rb").read())
        hashRelayFTP = hashlib.md5()
        hashRelayFTP.update(open(os.path.join(out, "testblock-2001-01-01.txt"), "rb").read())
        if hashRelayFTP.hexdigest() == hashControlFTP.hexdigest():
            print("File Transfer Success")
            log.log("[PASSED] A file was successfully uploaded to the test server, retrieved, and\ncompared to the original file by its md5 hash.")
        else:
            print("Error in File Transfer - Hashes Don't Match")
            print("Retrieve the testblock.txt file from the FTP server for comparison.")
            log.log("[FAILED] A file which was uploaded to the test server, and subsequently\nretrieved, did not match its original condition. Test this manually to ensure\nno problem exists in vsftpd and then re-examine the transfer functions in\nTapestry.")
        if countPlaced == 1 and listPlaced == ["testblock-2001-01-01.txt"]:
            print("grepBlocks works for FTP")
            log.log("[PASSED] The function to search by label and date on the server is working.")
        else:
            print("grepBlocks returned either the wrong count or list.")
            log.log("[FAILED] The FTP search function is not operating correctly. It will not be \npossible to retrieve files from the FTP site at present.")
    log.log("------------------------------------------------------------------------------")

    #  Clear Down!
    log.save()

    print("After passing this confirmation screen, the test result material will be deleted (except the log), including files on the FTP server. If you need to dissect further, leave this session open or delete the items manually yourself.")
    carryOn = input("Press any key to continue. > ")
    shutil.rmtree(out)
    if instFTP is not None:
        instFTP.delete("testblock-2001-01-01.txt")
    remKey = gpg.delete_keys(cfg.get("Environment Variables", "Expected FP"), secret=True, expect_passphrase=False)
    remKey = gpg.delete_keys(cfg.get("Environment Variables", "Expected FP"))

if __name__ == "__main__":
    runtime()