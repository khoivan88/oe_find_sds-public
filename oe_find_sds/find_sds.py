#!/usr/bin/python

"""
Author: Khoi Van

This program is designed specifically for Open Enventory to fix issue with
molecule missing sds (could not be extracted through "Read data from supplier")

This programs does:
    1. Connect into mysql database and find molecule in 'molecule' table
of specific database and find those molecule with missing sds
    2. Try to download sds files into a folder in /var/lib/mysql/missing_sds
    3. Update those sql entries with new downloaded sds files
"""


import getpass
import json
import os
import re
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import mysql.connector as mariadb
import requests
from bs4 import BeautifulSoup


download_path = r'/var/lib/mysql/missing_sds'
missing_sds = set()
debug = False
# print out extra info in debug mode in case SDS is not found
if len(sys.argv) == 2 and sys.argv[1] in ['--debug=True', '--debug=true', '--debug', '-d']:
    debug = True


def main(database, password):
    global download_path, debug

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
        print(f'Database: {database.upper()}')
        print('Getting molecules with missing SDS. Please wait!')
        # SDS found by OE that are marked as 'Acros' are corrupted, hence the query below
        query = ("SELECT distinct cas_nr FROM molecule WHERE cas_nr!='' AND (default_safety_sheet_blob is NULL or default_safety_sheet_by is NULL or default_safety_sheet_by='Acros')")
        try:
            cursor_select.execute(query)
        except mariadb.Error as error:
            print('Error: {}'.format(error))

        # Get the set of CAS for molecule missing sds in the database of interest:
        # https://stackoverflow.com/questions/7558908/unpacking-a-list-tuple-of-pairs-into-two-lists-tuples
        select_query_result = cursor_select.fetchall()
        # Exit out of the script if all SDS exist
        if not select_query_result:
            print('Nothing to download. Exiting!')
            exit()
            
        (to_be_downloaded, ) = zip(*select_query_result)
        # Get the unique CAS number set
        to_be_downloaded = set(to_be_downloaded)

        # Step 2: downloading sds file
        # Check if download path with the missing_sds directory exists. If not, create it
        # https://stackoverflow.com/questions/12517451/automatically-creating-directories-with-file-output
        # https://docs.python.org/3/library/os.html#os.makedirs
        os.makedirs(download_path, exist_ok=True)

        print('Downloading missing SDS files. Please wait!')

        download_result = []
        # # Using multithreading
        try:
            with Pool(10) as p:
                download_result = p.map(download_sds, to_be_downloaded)

        except Exception as error:
            if debug:
                traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
                print(traceback_str)

        # # Not using multithreading
        # # to_be_downloaded = ['9012-36-6']   # for testing only
        # try:
        #     for cas in to_be_downloaded:
        #         download_sds(cas)
        # except Exception as error:
        #     print(error)

        # Step 3: run UPDATE query to upload
        finally:
            # Sometimes Pool worker return 'None', remove 'None' as the following
            download_result = [x for x in download_result if x]

            print('Updating SQL table!')
            count_file_updated = 0
            # for cas in to_be_downloaded:
            for cas, downloaded, sds_source in download_result:
                try:
                    # run update_sql() and also increment the count for successful update
                    # update_sql() return 1 if success, otherwise return 0
                    count_file_updated += update_sql_sds(mariadb_connection, cas_nr=cas, sds_source=sds_source)
                except mariadb.Error as error:
                    print('Error: {}'.format(error))

            mariadb_connection.close()

            print('\nMolecules with missing SDS:')
            print(missing_sds)
            print(f'\nSummary for database {database.upper()}: ')
            print('\t{} SDS files are missing.'.format(len(missing_sds)))
            print('\t{} SDS files updated! '.format(count_file_updated))

            # Advice user about turning on debug mode for more error printing
            print('\n\n(Optional): you can turn on debug mode (more error printing during structure search) using the following command:')
            print('python oe_find_sds/find_sds.py  --debug\n')

    except mariadb.Error as error:
        if error.errno == mariadb.errorcode.ER_ACCESS_DENIED_ERROR:
            print("Wrong password!")
        elif error.errno == mariadb.errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
    else:
        mariadb_connection.close()


def download_sds(cas_nr: str) -> Tuple[str, bool, Optional[str]]:
    """Download SDS from variety of sources

    Parameters
    ----------
    cas_nr : str
        The CAS number of the molecule of interest

    Returns
    -------
    Tuple[str, bool, Optional[str]]
        - str: CAS number of the input chemical
        - bool: True if SDS file downloaded or exists
        - Optional[str]: the name of the SDS source or None
    """
    global download_path, debug
    '''This function is used to extract a single sds file
    See here for more info: http://stackabuse.com/download-files-with-python/'''

    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'}

    # Set initial return value for if SDS is downloaded (or existed)
    downloaded = False

    file_name = cas_nr + '.pdf'
    download_file = Path(download_path) / file_name
    # Check if the file not exists and download
    #check file exists: https://stackoverflow.com/questions/82831/how-do-i-check-whether-a-file-exists
    if download_file.exists():
        # print('{} already downloaded'.format(file_name))
        # print('.', end='')
        downloaded = True
        return cas_nr, downloaded, None

    else:
        print('\nSearching for {} ...'.format(file_name))
        try:
            # print('CAS {} ...'.format(file_name))

            sds_source, full_url = extract_download_url_from_chemblink(cas_nr) or \
                extract_download_url_from_vwr(cas_nr) or \
                extract_download_url_from_fisher(cas_nr) or \
                extract_download_url_from_tci(cas_nr) or \
                extract_download_url_from_chemicalsafety(cas_nr) or \
                extract_download_url_from_fluorochem(cas_nr) or \
                (None, None)

            # print('full url is: {}'.format(full_url))
            if full_url:    # extract with chemicalsafety
                r = requests.get(full_url, headers=headers, timeout=20)
                # Check to see if give OK status (200) and not redirect
                if r.status_code == 200 and len(r.history) == 0:
                    # print('\nDownloading {} ...'.format(file_name))
                    open(download_file, 'wb').write(r.content)
                    # print()
                    # return (0, sds_source)
                    downloaded = True
                    return (cas_nr, downloaded, sds_source)

            else:
            #     return download_sds_tci(cas_nr)    # May 5, 2020: TCI has updated to newer website, scraping currently not working
                return (cas_nr, downloaded, None)

        except Exception as error:
            # pass
            # raise ValueError('{}: SDS not found from Fisher, VWR, or FluoroChem/Oakwood'.format(cas_nr))
            if debug:
                traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
                print(traceback_str)
            return (cas_nr, downloaded, None)


def extract_download_url_from_vwr(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url to download SDS for chemical with cas_nr
    from https://us.vwr.com/store/search/searchMSDS.jsp

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

    Examples
    --------
    >>> print(extract_download_url_from_vwr(cas_nr='885051-07-0'))
    ('TCI America', 'https://us.vwr.com/assetsvc/asset/en_US/id/18065210/contents')
    """
    global debug

    adv_search_url = 'https://us.vwr.com/store/msds'.format(cas_nr)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
    }
    params = {
        'keyword' : cas_nr
    }

    if debug:
        print('Searching on https://us.vwr.com/store')

    try:
        with requests.Session() as s1:
            get_id = s1.get(adv_search_url, headers=headers, params=params, timeout=10)

            if get_id.status_code == 200 and len(get_id.history) == 0:
                html = BeautifulSoup(get_id.text, 'html.parser')
                # print(html.prettify())

                result_count_css = '.clearfix .pull-left'
                result_count = re.search(r'(\d+).*results were found', html.select(result_count_css)[0].text)[1]
                # print(result_count)

                # Check to make sure that there is at least 1 hit
                if result_count:
                    # Find first product
                    sds_link_css = 'td[data-title="SDS"] a'
                    sds_links = html.select(sds_link_css)
                    # print(sds_links[0]['href'])
                    full_url = sds_links[0]['href']

                    sds_manufacturer_css = 'td[data-title="Manufacturer"]'
                    sds_manufacturers = html.select(sds_manufacturer_css)
                    # print(sds_manufacturers[0].text)
                    sds_source = sds_manufacturers[0].text.strip()

                    return sds_source, full_url

                #     full_url = sds_links[0]['href']
                #     sds = s1.get(full_url)
                #     # print(sds.content)

                #     # Check to see if give OK status (200) and not redirect
                #     if sds.status_code == 200 and len(sds.history) == 0:
                #         # print('\nDownloading {} ...'.format(file_name))
                #         open('vwr0.pdf', 'wb').write(sds.content)

    except Exception as error:
        if debug:
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
        # return (cas_nr, downloaded, None)


def extract_download_url_from_chemblink(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url to download SDS for chemical with cas_nr
    from https://www.chemblink.com/

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

    Examples
    --------
    >>> print(extract_download_url_from_chemblink(cas_nr='681128-50-7'))
    ('Matrix', 'https://www.chemblink.com/MSDS/MSDSFiles/681128-50-7_Matrix.pdf')
    """

    global debug

    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
    }

    # get url from chemicalsafety.com to get url to download sds file
    extract_info_url = f'https://www.chemblink.com/MSDS/{cas_nr}_MSDS.htm'

    if debug:
        print('Searching on https://www.chemblink.com')

    try:
        r1 = requests.get(extract_info_url, headers=headers, timeout=20)
        # print(r1)

        # Check to see if give OK status (200) and not redirect
        if r1.status_code == 200 and len(r1.history) == 0:
            soup = BeautifulSoup(r1.text, 'html.parser')
            if soup:
                # Find all <a> tags with content "View / download", example: https://www.chemblink.com/MSDS/64-19-7_MSDS.htm
                # Example of a correct <a> tag for SDS download: '<a href="/MSDS/MSDSFiles/64-19-7_Alfa-Aesar.pdf" class="blue" onclick="blur()" target="_blank">View / download</a>'
                a_tags = soup.find_all('a', string=re.compile(r'View / download'))
                if a_tags:
                    domain = 'https://www.chemblink.com'
                    sds_link = a_tags[0]['href']
                    # Get source name from sds_link, example of sds_link href: '/MSDS/MSDSFiles/64-19-7_Alfa-Aesar.pdf'
                    source = re.search(r'\S+_(\S*)\.pdf', sds_link).group(1)
                    full_url = f'{domain}{sds_link}'
                    return source, full_url

    except Exception as error:
        # print('.', end='')
        if debug:
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
        # return None


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
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
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
        print('Searching on https://chemicalsafety.com/sds-search/')

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
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
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
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)
        # return None


def extract_download_url_from_tci(cas_nr: str) -> Optional[Tuple[str, str]]:
    """Search for url of SDS from TCI Chemicals (www.tcichemicals.com)

    Parameters
    ----------
    cas_nr : str
        The CAS number of the molecule of interest

    Returns
    -------
    Tuple[str, bool, Optional[str]]
        - str: CAS number of the input chemical
        - bool: True if SDS file downloaded or exists
        - str: the name of the SDS source or None
    """
    global debug

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
    }

    adv_search_url = 'https://www.tcichemicals.com/US/en/search/?text={}&resulttype=product'.format(cas_nr)

    # # Set initial return value for if SDS is downloaded (or existed)
    # downloaded = False

    # file_name = cas_nr + '.pdf'
    # # download_file = Path(download_path) / file_name

    if debug:
        print('Searching on https://www.tcichemicals.com')

    try:
        with requests.Session() as s:
            get_id = s.get(adv_search_url, headers=headers, timeout=10)

            if get_id.status_code == 200 and len(get_id.history) == 0:
                # get_id.text
                html = BeautifulSoup(get_id.text, 'html.parser')
                # print(html.prettify()); exit(1)

                # Get the token, required for POST request for SDS file name later
                csrf_token = html.find('input', attrs={'name': 'CSRFToken'})['value']
                # print(csrf_token)

                region_code = html.find_all(string=re.compile(r'(encodedContextPath[^;]+?;)'))
                # print(region_code[0])
                encodedContextPath = re.search(r'(encodedContextPath[^;]+?\'(\S+)\';)', region_code[0])[2].replace('\\' ,'')
                # print(encodedContextPath)

                product_cat_css = 'div#contentSearchFacet > span.facet__text:first-child > a:first-child'
                product_category = html.select(product_cat_css)[0]
                # print(product_category)

                hit_count = 0
                if product_category.text == 'Products':
                    hit_count = re.search(r'\((\d+)\)',
                                        html.select(f'{product_cat_css} + span.facet__value__count')[0].text)[1]
                # print(hit_count)

                # Check to make sure that there is at least 1 hit
                if hit_count:
                    # Find the first hit
                    first_hit_div = html.find('div', class_='prductlist')
                    # print(first_hit_form)

                    # Find the CAS# for the first hit
                    returned_cas = first_hit_div['data-casno']
                    # print(returned_cas)

                    # Confirm the first hit has the same CAS# as search chemical
                    if returned_cas == cas_nr:
                        # Get this TCI product number as follow:
                        prd_id = first_hit_div['data-id']
                        # print(prd_id)

                        # Check if TCI product number is found:
                        if prd_id:
                            sds_url = ' https://www.tcichemicals.com/US/en/documentSearch/productSDSSearchDoc'

                            data = {
                                'productCode': f'{prd_id}',
                                'langSelector': 'en',
                                'selectedCountry': 'US',
                                'CSRFToken': f'{csrf_token}'
                            }
                            file_name_res = s.post(sds_url, timeout=15, data=data)
                            # print(file_name_res)
                            # print(file_name_res.headers)
                            # print(file_name_res.headers.get('content-disposition'))

                            # Get the SDS file name using the return header, in "content-disposition"
                            res_file = re.search(r'filename=(\S+)$', file_name_res.headers.get('content-disposition'))[1]

                            # url = f'https://www.tcichemicals.com/US/en/sds/{prd_id.upper()}_US_EN.pdf'
                            # An example of an sds url: 'https://www.tcichemicals.com/US/en/sds/B3296_US_EN.pdf'
                            url = f'https://www.tcichemicals.com{encodedContextPath}/sds/{res_file}'
                            # print(url)

                            return 'TCI', url

    except Exception as error:
        if debug:
            traceback_str = ''.join(traceback.format_exception(etype=type(error), value=error, tb=error.__traceback__))
            print(traceback_str)


def update_sql_sds(mariadb_connection, cas_nr: str, sds_source: str = 'SDS') -> int:
    """Update SQL database by uploading the downloaded SDS pdf files

    Parameters
    ----------
    mariadb_connection : mysql.connector Object
        an established connection to the SQL database
    cas_nr : str
        the CAS number of molecule that needs to be updated with new SDS
    sds_source : str, optional
        the name of the SDS source, by default 'SDS'

    Returns
    -------
    int
        1: if success
        0: if not, the cas_nr will also be added into global missing_sds set
    """
    global download_path, missing_sds
    cursor_update = mariadb_connection.cursor(buffered=True)
    sds_file = Path(download_path) / '{}.pdf'.format(cas_nr)
    # print(file_path)

    # if molfile exists or downloaded
    if sds_file.exists():
        sds_source = 'SDS' if sds_source is None else sds_source
        print('CAS# {:20}: '.format(cas_nr), end='')
        query = ("UPDATE molecule SET default_safety_sheet_blob=LOAD_FILE('{}'), default_safety_sheet_by='{}', default_safety_sheet_url=NULL, default_safety_sheet_mime='application/pdf' WHERE cas_nr='{}'".format(sds_file, sds_source, cas_nr))
        cursor_update.execute(query)
        mariadb_connection.commit()
        # cursor_update.execute("flush table molecule")
        print('\tSDS uploaded successfully!')
        return 1

    # extracting_mol return the cas# of those that it could not find mol file
    else:
        # Add the cas_nr into global missing_sds set
        missing_sds.add(cas_nr)
        return 0


if __name__ == '__main__':
    # Require user running this python as root for creating download_path
    is_root = input('Are you login as root user? (y/n): ')
    if (is_root not in ['y', 'yes']):
        print('You need to convert to root user before running this program (or run with `sudo`) ')
        exit(1)    # Comment this line out if you have change the download_path to a location that you have read and write permissions.

    # Get user input for root password and the database needs to be updated
    # to hide password input: https://stackoverflow.com/questions/9202224/getting-command-line-password-input-in-python
    password = getpass.getpass('Please type in the password for MySQL "root" user: ')
    database = input('Please type in the name of the database needs updating: ')
    # Ask user to retype the database name and if it does NOT match, exit the programs
    database2 = input('Please re-type the name of the database to confirm: ')
    if (database != database2):
        print('Database names do NOT match!')
        exit(2)

    main(database=database, password=password)
