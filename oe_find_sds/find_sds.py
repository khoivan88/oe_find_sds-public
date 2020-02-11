#!/usr/bin/python

"""
This program is designed specifically for Open Enventory to fix issue with
molecule missing sds (could not be extracted through "Read data from supplier")

This programs does:
    1. Connect into mysql database and find molecule in 'molecule' table
of specific database and find those molecule with missing sds
    2. Try to download sds files into a folder in /var/lib/mysql/missing_sds
    3. Update those sql entries with new downloaded sds files

Version 5:
    - Incorporated result from Fluorochem
    - Fixing bug with existing default_safety_sheet_url and default_safety_sheet_mime
    by setting them to NULL

Version 4:
    - Testing using cheminfo.org/webservices by extracting catalog number from 
    http://www.fluorochem.co.uk/

Version 3:
    - Refractored extracting url download into its own method
    - Added extracting url download from chemicalsafety.com

Version 2:
    - Added asking if user is root and password
    - Added asking what database to be modified
    - Switch to extracting data from https://www.fishersci.com because Chemexper
    has limited requests

"""


import getpass
import json
import os
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import mysql.connector as mariadb
import requests
# import wget
from bs4 import BeautifulSoup

download_path = '/var/lib/mysql/missing_sds'
missing_sds = set()
debug = False


def main():
    global download_path
    # Require user running this python as root
    if_root = input('Are you login as root user? (y/n): ')
    if (if_root not in ['y', 'yes']):
        print('You need to convert to root user before running this program')
        exit(1)
    # Get user input for root password and the database needs to be updated
    # to hide password input: https://stackoverflow.com/questions/9202224/getting-command-line-password-input-in-python
    password = getpass.getpass('Please type in the password for MySQL "root" user: ')
    database = input('Please type in the name of the database needs updating: ')
    # Ask user to retype the database name and if it does NOT match, exit the programs
    database2 = input('Please re-type the name of the database to confirm: ')
    if (database != database2):
        print('Database names do NOT match!')
        exit(2)

    """
    Info for mysql connection and query can be found here:
     https://mariadb.com/resources/blog/how-connect-python-programs-mariadb
     https://dev.mysql.com/doc/connector-python/en/connector-python-tutorial-cursorbuffered.html

    Handling error in password or database not exists:
    https://dev.mysql.com/doc/connector-python/en/connector-python-example-connecting.html
    https://dev.mysql.com/doc/connector-python/en/connector-python-api-errorcode.html
    """

    # Open a connection to mysql
    try:
        mariadb_connection = mariadb.connect(user='root', password=password, database=database)
        # Create a cursor in the sql table using the open connection
        cursor_select = mariadb_connection.cursor(buffered=True)

        # Step1: run SELECT query to find CAS#
        print('Getting molecules with missing SDS. Please wait!')
        query = ("SELECT distinct cas_nr FROM molecule WHERE cas_nr!='' AND (default_safety_sheet_by is NULL or default_safety_sheet_by='Acros')")
        try:
            cursor_select.execute(query)
        except mariadb.Error as error:
            print('Error: {}'.format(error))

        # Get the set of CAS for molecule missing sds in the database of interest:
        # https://stackoverflow.com/questions/7558908/unpacking-a-list-tuple-of-pairs-into-two-lists-tuples
        (to_be_downloaded, ) = zip(*cursor_select.fetchall())
        to_be_downloaded = set(to_be_downloaded)

        # Step 2: downloading sds file
        # Check if download path with the missing_sds directory exists. If not, create it
        # https://stackoverflow.com/questions/12517451/automatically-creating-directories-with-file-output
        # https://docs.python.org/3/library/os.html#os.makedirs
        os.makedirs(download_path, exist_ok=True)

        print('Downloading missing SDS files. Please wait!')
        # # Using multithreading
        try:
            with Pool(10) as p:
                p.map(download_sds, to_be_downloaded)
        # except ValueError as error_1:
        #     print('.', end='')
        except Exception as error:
            print(error)

        # # Not using multithreading
        # # to_be_downloaded = ['9012-36-6']   # for testing only
        # try:
        #     for cas in to_be_downloaded:
        #         download_sds(cas)
        # except Exception as error:
        #     print(error)

        # Step 3: run UPDATE query to upload
        finally:
            print('Updating SQL table!')
            count_file_updated = 0
            # for cas in downloaded_sds:
            for cas in to_be_downloaded:
                try:
                    # run update_sql() and also increment the count for successful update
                    # update_sql() return 1 if successs, otherwise return 0
                    count_file_updated += update_sql_sds(mariadb_connection, cas)
                except mariadb.Error as error:
                    print('Error: {}'.format(error))

            mariadb_connection.close()
            print(missing_sds)
            print('\nSummary: ')
            print('\t{} SDS files are missing: '.format(len(missing_sds)))
            print('\t{} SDS files updated! '.format(count_file_updated))

            # Advice user about turning on debug mode for more error printing
            print('\n\n(Optional): you can turn on debug mode (more error printing during structure search) using the following command:')
            print('python oe_find_sds/find_sds.py  --debug')

    except mariadb.Error as err:
        if err.errno == mariadb.errorcode.ER_ACCESS_DENIED_ERROR:
            print("Wrong password!")
        elif err.errno == mariadb.errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    else:
        mariadb_connection.close()


def download_sds(cas_nr: str) -> int:
    """This function takes cas_nr and try to download its SDS
    
    Parameters
    ----------
    cas_nr : str
        the CAS# for a chemical of interests
    
    Returns
    -------
    int
        -1: if download file already exists
        0: if download successful
        1: if there is error
    
    """
    global download_path, debug
    '''This function is used to extract a single sds file
    See here for more info: http://stackabuse.com/download-files-with-python/'''

    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'}

    file_name = cas_nr + '.pdf'
    download_file = Path(download_path) / file_name
    # Check if the file not exists and download
    #check file exists: https://stackoverflow.com/questions/82831/how-do-i-check-whether-a-file-exists
    if download_file.exists():
        # print('{} already downloaded'.format(file_name))
        print('.', end='')
        return -1
    else:
        print('\nSearching {} ...'.format(file_name))
        try:
            # print('CAS {} ...'.format(file_name))
            sds_source, full_url = extract_download_url_from_fisher(cas_nr) or (None, None)
            if full_url is None:    # extract with chemicalsafety
                sds_source, full_url = extract_download_url_from_chemicalsafety(cas_nr) or (None, None)
            if full_url is None:    # extract with fluorochem
                sds_source, full_url = extract_download_url_from_fluorochem(cas_nr) or (None, None)
            # print('full url is: {}'.format(full_url))
            if full_url:    # extract with chemicalsafety
                r = requests.get(full_url, headers=headers, timeout=20)
                # Check to see if give OK status (200) and not redirect
                if r.status_code == 200 and len(r.history) == 0:
                    # print('\nDownloading {} ...'.format(file_name))
                    open(download_file, 'wb').write(r.content)
                    print()
                    return 0
            else:
                return 1
        except Exception as error:
            # pass
            # raise ValueError('{}: SDS not found from Fisher, VWR, or FluoroChem/Oakwood'.format(cas_nr))
            if debug:
                print(error)
            return 1
            # print("Could not find SDS")


def extract_download_url_from_fisher(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url to download SDS for chemical with cas_nr
    from https://www.fishersci.com
    
    Parameters
    ----------
    cas_nr : str
        CAS# for chemical of interest
    
    Returns
    -------
    Optional[Tuple[str, str]]
        Tuple[str, str]:
            the name of the SDS source
            the URL from Fisher for SDS file
        None: if URL cannot be found
    """
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'}

    # get url from Fisher to get url to download sds file
    extract_info_url = 'https://www.fishersci.com/us/en/catalog/search/sds'
    payload = {'selectLang': 'EN',
            'msdsKeyword': cas_nr}

    if debug:
        print('Searching on https://www.fishersci.com/us/en/catalog/search/sdshome.html')

    try:
        r = requests.get(extract_info_url, headers=headers, timeout=10, params=payload)
        # Check to see if give OK status (200) and not redirect
        if r.status_code == 200 and len(r.history) == 0:
            # BeautifulSoup ref: https://www.digitalocean.com/community/tutorials/how-to-scrape-web-pages-with-beautiful-soup-and-python-3
            # Using BeautifulSoup to scrap text
            html = BeautifulSoup(r.text, 'html.parser')
            # The list of found sds is in class 'catalog_num', with each item in class 'catlog_items'
            # cat_no_list = html.find(class_='catalog_num')    # This is to find all of the sds

            # Check if there is error message. Fisher automatically does a close search with error message
            error_message = html.find(class_='errormessage search_results_error_message')
            cat_no_list = html.find(class_='catlog_items')    # This will find the first sds
            
            if (not error_message) and cat_no_list:
                cat_no_items = cat_no_list.find_all('a')   #
                # download info
                rel_download_url = cat_no_items[0].get('href')
                catalogID = cat_no_items[0].contents[0]
                full_url = 'https://www.fishersci.com' + rel_download_url
                # print(f'rel_download_url is {rel_download_url}')
                return 'Fisher', full_url


    except Exception as error:
        # print('.', end='')
        if debug:
            print(error)
        # return None


def extract_download_url_from_chemicalsafety(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url to download SDS for chemical with cas_nr
    from https://chemicalsafety.com/sds-search/
    
    Parameters
    ----------
    cas_nr : str
        CAS# for chemical of interest
    
    Returns
    -------
    Optional[Tuple[str, str]]
        Tuple[str, str]:
            the name of the SDS source
            the URL from Fisher for SDS file
        None: if URL cannot be found
    """
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
        'accept-encoding': 'gzip, deflate, br',
        'content-type': 'application/json'}
    # get url from chemicalsafety.com to get url to download sds file
    extract_info_url = 'https://chemicalsafety.com/sds1/retriever.php'
    form1 = {
        "action": "search", 
        "p1": "MSMSDS.COMMON|",
        "p2": "MSMSDS.MANUFACT|", 
        "p3": "MSCHEM.CAS|" + cas_nr,
        "hostName": "chemicalsafety.com", 
        "isContains": "0"
        }

    if debug:
        print('Searching on chemicalsafety.com/sds-search')

    try:
        r1 = requests.post(extract_info_url, headers=headers, 
                data=json.dumps(form1), timeout=20)
        # Check to see if give OK status (200) and not redirect
        if r1.status_code == 200 and len(r1.history) == 0:
            id_list = r1.json()['rows']
            msds_id = ''
            for item in id_list:
                if item[3] == cas_nr:
                    msds_id = item[0]
                    break
            if msds_id != '':
                form2 = {"action": "msdsdetail",
                        "p1": msds_id,
                        "p2": "",
                        "p3": "",
                        "isContains": ""}
                r2 = requests.post(extract_info_url, headers=headers, 
                        data=json.dumps(form2), timeout=20)
                result = r2.json()['rows'][0]
                #Confirm the msds_id and cas_nr:
                if msds_id == result[0] and cas_nr == result[3]:
                    sds_pdf_file = result[10].rstrip(',')
                    form3 = {"action":"getpdfurl","p1":sds_pdf_file,"p2":"","p3":"","isContains":""}
                    r3 = requests.post(extract_info_url, headers=headers, data=json.dumps(form3), timeout=20)
                    #Get the url
                    # Translate curl to python https://curl.trillworks.com/
                    # urllib.parse doc: https://docs.python.org/3.6/library/urllib.parse.html
                    full_url = r3.json()['url']
                    return 'ChemicalSafety', full_url
    except Exception as error:
        # print('.', end='')
        if debug:
            print(error)
        # return None


def extract_download_url_from_fluorochem(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url to download SDS for chemical with cas_nr
    from http://www.fluorochem.co.uk/
    
        
    Parameters
    ----------
    cas_nr : str
        CAS# for chemical of interest
    
    Returns
    -------
    Optional[Tuple[str, str]]
        Tuple[str, str]:
            the name of the SDS source
            the URL from Fisher for SDS file
        None: if URL cannot be found
    """
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
        'Content-Type': 'application/json', }

    url = 'http://www.fluorochem.co.uk/Products/Search'
    payload = {
        "lstSearchType": "C",
        "txtSearchText": cas_nr,
        "showPrices": 'false',
        "showStructures": 'false',
        "groupFilters": []}

    if debug:
        print('Searching on fluorochem.co.uk')

    try:
        r = requests.post(url, headers=headers, timeout=20, data=json.dumps(payload))
        # No need to check if requests give OK status (200) and not redirect because
        # fluorochem return code 200 without redirect with error

        # BeautifulSoup ref: https://www.digitalocean.com/community/tutorials/how-to-scrape-web-pages-with-beautiful-soup-and-python-3
        # Using BeautifulSoup to scrap text
        html = BeautifulSoup(r.text, 'html.parser')
        if html:
            result = html.find_all('td')
            if result:
                # info = [item.contents[0] for item in result]
                # cat_no_1 = info[0]
                # cas = info[2]
                cat_no_2 = html.find(class_='textLink prodDetailLink').get('prodcode')
                # confirming cas# and catalog number
                # if cas == cas_nr and cat_no_1 == cat_no_2:
                # download info
                download_url = 'https://www.cheminfo.org/webservices/msds?brand=fluorochem&catalog={}&embed=true'
                full_url = download_url.format(cat_no_2)
                return 'Fluorochem', full_url
    except Exception as error:
        #     print('.', end='')
        if debug:
            print(error)
        # return None


def update_sql_sds(mariadb_connection, cas_nr: str, sds_source: str = 'SDS') -> int:
    global download_path
    cursor_update = mariadb_connection.cursor(buffered=True)
    file_path = download_path + '/{}.pdf'.format(cas_nr)
    sds_file = Path(file_path)
    # print(file_path)

    # if molfile exists or downloaded (extracting_mol return -1 or 0)
    if sds_file.exists():
        print('CAS# {:20}: '.format(cas_nr), end='')
        query = ('''UPDATE molecule 
            SET default_safety_sheet_blob=LOAD_FILE('{}'), 
                default_safety_sheet_by='{}', 
                default_safety_sheet_url=NULL, 
                default_safety_sheet_mime='application/pdf' 
            WHERE cas_nr={}'''.format(file_path, sds_source, cas_nr))
        cursor_update.execute(query)
        mariadb_connection.commit()
        # cursor_update.execute("flush table molecule")
        print('\tSDS uploaded successfully!')
        return 1
    # extracting_mol return the cas# of those that it could not find mol file
    else:
        missing_sds.add(cas_nr)
        return 0


if __name__ == '__main__':
    main()
