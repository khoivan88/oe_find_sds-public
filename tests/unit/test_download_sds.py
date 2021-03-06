import sys, os
sys.path.append(os.path.realpath('oe_find_sds'))

import re
import pytest
from unittest.mock import patch
from oe_find_sds.find_sds import download_sds


def mock_raise_exception():
    # return pytest.raises(RuntimeError)
    raise RuntimeError()


@pytest.mark.parametrize(
    "cas_nr, expect", [
        # ('623-51-8', ('623-51-8', True, 'Fisher')),
        # ('28697-53-2', ('28697-53-2', True, 'Fisher')),
        # ('1450-76-6', ('1450-76-6', True, 'ChemicalSafety')),
        # ('00000-00-0', ('00000-00-0', False, None)),
        # ('623-51-8', ('623-51-8', True, 'Fisher')),
        # ('28697-53-2', ('28697-53-2', True, 'Acros Organics')),
        # ('1450-76-6', ('1450-76-6', True, 'ChemicalSafety')),
        # ('1450-76-6', ('1450-76-6', True, 'TCI America')),
        # ('623-51-8', ('623-51-8', True, 'TCI America')),
        ('623-51-8', ('623-51-8', True, 'Alfa-Aesar')),
        ('28697-53-2', ('28697-53-2', True, 'Oakwood')),
        ('1450-76-6', ('1450-76-6', True, 'Sigma-Aldrich')),
        ('681128-50-7', ('681128-50-7', True, 'Matrix')),
        ('950194-37-3', ('950194-37-3', True, 'TCI')),
        ('885051-07-0', ('885051-07-0', True, 'TCI')),
        ('00000-00-0', ('00000-00-0', False, None)),
    ]
)
def test_download_sds_without_existing_files(tmpdir, monkeypatch, cas_nr, expect):
    '''Test download_sds() WITHOUT existing mol files'''

    '''Changing the value of 'debug' variable to True for extra info'''
    monkeypatch.setattr("oe_find_sds.find_sds.debug", True)

    '''Changing the value of 'download_path' variable to tmpdir'''
    # print('tmpdir is: {}'.format(tmpdir))
    monkeypatch.setattr("oe_find_sds.find_sds.download_path", tmpdir)

    result = download_sds(cas_nr)
    assert result == expect


@pytest.mark.parametrize(
    "cas_nr, expect", [
        ('623-51-8', ('623-51-8', True, None)),
        ('28697-53-2', ('28697-53-2', True, None)),
        ('1450-76-6', ('1450-76-6', True, None)),
        ('00000-00-0', ('00000-00-0', False, None)),
    ]
)
def test_download_sds_with_existing_files(tmpdir, monkeypatch, cas_nr, expect):
    '''Test download_sds() WITH existing mol files'''

    '''Changing the value of 'debug' variable to True for extra info'''
    monkeypatch.setattr("oe_find_sds.find_sds.debug", True)

    '''Changing the value of 'download_path' variable to tmpdir'''
    # print('tmpdir is: {}'.format(tmpdir))
    monkeypatch.setattr("oe_find_sds.find_sds.download_path", tmpdir)

    '''Run the download once to simulate existing file'''
    download_sds(cas_nr)

    result = download_sds(cas_nr)
    assert result == expect


@pytest.mark.parametrize(
    "cas_nr, expect", [
        # ('623-51-8', ('623-51-8', False, None)),
        ('00000-00-0', ('00000-00-0', False, None)),
    ]
)
def test_download_sds_with_error(tmpdir, monkeypatch, cas_nr, expect):
    '''Test download_sds() WITHOUT existing mol files'''

    '''Changing the value of 'debug' variable to True for extra info'''
    monkeypatch.setattr("oe_find_sds.find_sds.debug", True)

    '''Changing the value of 'download_path' variable to tmpdir'''
    # print('tmpdir is: {}'.format(tmpdir))
    monkeypatch.setattr("oe_find_sds.find_sds.download_path", tmpdir)

    monkeypatch.setattr('oe_find_sds.find_sds.extract_download_url_from_fisher', mock_raise_exception)

    result = download_sds(cas_nr)
    assert result == expect
