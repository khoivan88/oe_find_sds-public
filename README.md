[![Python 3](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/python-3-shield.svg)](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/)
[![Updates](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/shield.svg)](https://pyup.io/repos/github/khoivan88/oe_find_sds-public/)
[![codecov](https://codecov.io/gh/khoivan88/oe_find_sds-public/branch/master/graph/badge.svg)](https://codecov.io/gh/khoivan88/oe_find_sds-public)
[![python version](https://img.shields.io/badge/python-v3.6%2B-blue)]()


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
2. Try to download sds files into a folder in `/var/lib/mysql/missing_sds` (For Linux environment with LAMP stack)
3. Update those SQL entries with new downloaded sds files


## REQUIREMENTS

- Python 3.6+
- Linux machine root access to the server hosting Open Enventory (to create a download folder if not existed). If user does not have root account (or sudo), you can:
  1. Change the `download_path` to a different location that you have read and write permission.
  2. Comment out [`exit(1)`](oe_find_sds/find_sds.py#L699) in `find_sds.py` file


## USAGE

1. Clone this repository:

   ```bash
   git clone https://github.com/khoivan88/oe_find_sds-public.git    #if you have git
   # if you don't have git, you can download the zip file then unzip
   ```

2. Change into the directory of the program:

   ```bash
   cd oe_find_sds-public
   ```

> ---
> **_NOTE_**
>
> - This file is made for **Linux** environment, you should be able
>   to used it on other OS by changing the location of the ["download_path"](oe_find_sds/find_sds.py#L32)
>   - Make sure you use an **absolute path**
>   - For **Windows**:
>     - Use of either forward slashes (`/`) or backward slashes (`\`) should be ok!
>     - If you use XAMPP (or similar PHP, Apache, SQL package), you can try this path:
>
>       ```python
>       download_path = r'C:/xampp/mysql/data/missing_sds'
>       ```
> ---

3. (Optional): create virtual environment for python to install dependency:
   Note: you can change `oe_find_sds_venv` to another name if desired.

   ```bash
   python -m venv oe_find_sds_venv   # Create virtual environment
   source oe_find_sds_venv/bin/activate    # Activate the virtual environment on Linux
   # oe_find_sds_venv\Scripts\activate    # Activate the virtual environment on Windows
   ```

4. Install python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run the program:

   ```bash
   python oe_find_sds/find_sds.py
   ```

   - Answer questions for:
     - confirming running under root
     - mySQL root password (typing password will not be shown on screen)
     - the name of the database you want to update (twice to confirm)
<br/>


## VERSIONS
See [here](VERSION.md) for the most up-to-date
