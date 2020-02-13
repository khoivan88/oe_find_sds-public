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
2. Try to download sds files into a folder in `/var/lib/mysql/missing_sds`
3. Update those SQL entries with new downloaded sds files


## REQUIREMENTS

- Python 3+
- Linux machine root access to the server hosting Open Enventory (to create a download folder if not existed). If user does not have root account (or sudo), you can:
  1. Change the `download_path` to a different location that you have read and write permission.
  2. Comment out [`exit(1)`](oe_find_sds/find_sds.py#L45) in `find_sds.py` file
- This file is made for **Linux** environment, you should be able
  to used it on other OS by changing the location of the ["download_path"](oe_find_sds/find_sds.py#L30)


## USAGE

After cloning this repo onto the Open Enventory server:

1. Clone this repository:
   
   ```bash
   git clone https://github.com/khoivan88/oe_find_sds-public.git    #if you have git
   # if you don't have git, you can download the zip file then unzip
   ```

2. Change into the directory of the program:
   
   ```bash
   cd oe_find_sds-public
   ```

2. (Optional): create virtual environment for python to install dependency:
   Note: you can change `oe_find_sds_venv` to another name if desired.

   ```bash
   python3 -m venv oe_find_sds_venv   # Create virtual environment
   source oe_find_sds_venv/bin/activate    # Activate the virtual environment on Linux
   # oe_find_sds_venv/Scripts/activate    # Activate the virtual environment on Windows
   ```

3. Install python dependencies:
   
   ```bash
   pip install -r requirements.txt
   ```

4. Run the program:
   
   ```bash
   python3 oe_find_sds/find_sds.py
   ```

   - Answer questions for:
     - confirming running under root
     - mySQL root password (typing password will not be shown on screen)
     - the name of the database you want to update (twice to confirm)
<br/>


## VERSIONS
See [here](VERSION.md) for the most up-to-date
