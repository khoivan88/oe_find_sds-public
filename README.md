[![Python 3](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/python-3-shield.svg)](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/)
[![Updates](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/shield.svg)](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/)


# FIND MISSING SDS FOR CHEMICALS IN OPEN ENVENTORY
<br/>
This program is designed specifically for Open Enventory to fix issue with
molecule missing sds (could not be extracted through "Read data from supplier")
This programs does:

## CONTENTS
- [Details](#details)
- [Requirements](#requirements)
- [Usage](#usage)
- [Versions](#versions)

<br/>

## DETAILS
This programs does:
1. Connect into mysql database and find molecule in 'molecule' table
of specific database and find those molecule with missing sds
2. Try to download sds files into a folder in /var/lib/mysql/missing_sds
3. Update those sql entries with new downloaded sds files


## REQUIREMENTS

- root access to the server hosting Open Enventory
- Python 3+
- This file is made for Linux environment, you should be able
  to used it on other OS with changing the location of the "download_path"


## USAGE

After cloning this repo onto the Open Enventory server:

1. Change into directory of the new file:
   
   ```bash
   cd find_missing_sds-public
   ```

2. (Optional): create virtual environment for python to install dependency:
   
   ```bash
   # you can change "find_missing_sds_venv" to another name too
   python3 -m venv find_missing_sds_venv   # Create virtual environment
   source find_missing_sds_venv/bin/activate    # Activate the virtual environment
   ```

3. Install python dependencies:
   
   ```bash
   pip install -r requirements.txt
   ```

4. Run the program:
   
   ```bash
   # Replace "find_missing_sds_v5" with latest version if neccessary
   python3 find_missing_sds_v5/find_missing_sds.py
   ```

   - Answer questions for:
     - confirming running under root
     - mySQL root password (typing password will not be shown on screen)
     - the name of the database you want to update (twice to confirm)
<br/>


## VERSIONS

### Version 5:
- Incorporated result from Fluorochem
- Fixing bug with existing default_safety_sheet_url and default_safety_sheet_mime
    by setting them to NULL


### Version 4:
- Testing using cheminfo.org/webservices by extracting catalog number from fluorochem


### Version 3:
- Refactor extracting url download into its own method
- Add extracting url download from chemicalsafety.com


### Version 2:
- Add asking if user is root and password
- Add asking what database to be modified
- Switch to extracting data from https://www.fishersci.com because Chemexper
    has limited requests
