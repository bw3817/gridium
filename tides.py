"""
This module provides functionality to scrape tide forecast web site.
(https://www.tide-forecast.com/) and deliver information on
low tides that occur after sunrise and before sunset.

Requires packages:
requests
beautifulsoup4
"""

from collections import defaultdict
from datetime import datetime, date, time

import requests
from bs4 import BeautifulSoup, element as bs4_element


BASE_URL = "https://www.tide-forecast.com"
TIDE_CLASS = "tide-day-tides"
DATE_FORMAT = "%a %d %B"
TIME_FORMAT = "%I:%M%p"


class ScrapeTides:
    """
    This class provides functionality to scrape tide forecast site
    (https://www.tide-forecast.com/)
    """

    @staticmethod
    def parse_location(location):
        """
        Given a city, state combination, returns a string suitable for searching.
        :param location: str
        :return: str
        """
        city, state = location.strip().split(',')
        return f"{city.strip().replace(' ', '-')}-{state.strip().replace(' ', '-')}"

    @staticmethod
    def get_location_without_state(location):
        city, state = location.strip().split(',')
        return f"{city.strip().replace(' ', '-')}"

    @staticmethod
    def force_hour_two_digits(time_str):
        def fix_hour(hr):
            return '12' if hr[-2:] == '00' else hr[-2:]
        left_part, right_part = ('0' + time_str.strip()).split(':')
        return fix_hour(left_part) + ':' + right_part

    def parse_time_str(self, time_str):
        """
        Convert time string to a Python time.
        :param time_str: str
        :param time_format: str
        """
        try:
            return datetime.strptime(self.force_hour_two_digits(time_str), TIME_FORMAT).time()
        except ValueError:
            return None

    @staticmethod
    def adjust_year(date_obj):
        """
        Adjust year for the date object provided.
        :param date_obj: Python date object
        :return: Python date object
        """
        today = date.today()
        if today.month == 12:
            if date_obj.month == 1:
                return date_obj.replace(year=today.year + 1)
        return date_obj.replace(year=today.year)

    def parse_date_str(self, date_str, date_format=DATE_FORMAT):
        """
        Convert date string to a Python date.
        :param date_str: str
        :param date_format: str
        """
        try:
            return self.adjust_year(datetime.strptime(date_str, date_format).date())
        except ValueError:
            return None

    @staticmethod
    def has_tide_info(tr, tide_type='low'):
        tds = tr.find_all('td')
        for td in tds:
            if f'tide-table__part--{tide_type}' in td.attrs['class']:
                return True
        return False

    @staticmethod
    def get_value_height_unit(container):
        value = container.find('span', attrs={'class': 'tide-table__value-low'})
        height = container.find('span', attrs={'class': 'tide-table__height'})
        units = container.find('span', attrs={'class': 'tide-table__units'})
        return value, height, units

    def get_data(self, td):
        data = list()
        divs = td.find_all('div')

        if len(divs) == 1:
            value, height, units = self.get_value_height_unit(td)
            if all((value, height, units)):
                row = (self.parse_time_str(value.text), float(height.text), units.text)
                data.append(row)
        elif len(divs) == 2:
            for div in divs:
                value, height, units = self.get_value_height_unit(div)
                if all((value, height, units)):
                    row = (self.parse_time_str(value.text), float(height.text), units.text)
                    data.append(row)

        return data

    def get_tides(self, table, dates_from_table):
        """
        Parse HTML table and retrieve tides.
        :param table: BeautifulSoup object representing an HTML table
        :param dates_from_table: list
        :param rise_and_set: list of tuples, each a pair of Python time objects
        :return: dict
        """
        tides = defaultdict(list)
        trs = table.find_all('tr', attrs={'class': 'tide-table__separator'})
        for tr in trs:
            if not self.has_tide_info(tr, 'low'):
                continue

            day = 0
            td_index = 0
            tds = tr.find_all('td')

            while True:
                if td_index >= len(tds):
                    return tides

                td = tds[td_index]
                dt, cols = dates_from_table[day]

                if cols == 0:
                    tides[dt] = self.get_data(td)
                    td_index += 1
                else:
                    for _ in range(0, cols):
                        td = tds[td_index]
                        data = self.get_data(td)
                        if data:
                            tides[dt].extend(data)
                        td_index += 1

                day += 1

    def get_rise_and_set(self, table):
        for tr in table.find_all('tr'):
            tds = tr.find_all('td', attrs={'class': 'tide-table__part--sun'})
            if not tds:
                continue

            times_ = list()
            sunrise = None
            sunset = None

            for td in tds:
                if not td.text:
                    continue

                if sunrise is None:
                    div = td.find('div')
                    sunrise = self.parse_time_str(div.text.strip())
                elif sunset is None:
                    div = td.find('div')
                    sunset = self.parse_time_str(div.text.strip())
                else:
                    divs = td.find_all('div')
                    data = [self.parse_time_str(div.text.strip()) for div in divs]
                    if data and data != [None, None]:
                        times_.append(data)

            if sunrise and sunset:
                times_.insert(0, [sunrise, sunset])
            return times_

    @staticmethod
    def get_dates_from_table(table):
        """
        Parse HTML table and retrieve tides.
        :param table: BeautifulSoup object representing an HTML table
        :return: list
        """
        ths = table.find_all('th', attrs={'class': 'tide-table__day'})
        return [
            (date.fromisoformat(th.attrs['data-date']), int(th.attrs.get('colspan', 0)))
            for th in ths
        ]

    def get_from_url(self, url):
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        table = soup.find('table', attrs={'class': 'tide-table__table'})
        if table:
            return table

    def get_table(self, location):
        parsed_location = self.parse_location(location)
        url = f"{BASE_URL}/locations/{parsed_location}/tides/latest"
        table = self.get_from_url(url)
        if table:
            return table

        # page = requests.get(url)
        # soup = BeautifulSoup(page.text, "html.parser")
        # table = soup.find('table', attrs={'class': 'tide-table__table'})

        # location not found; try without state name
        location_without_state = self.get_location_without_state(location)
        url = f"{BASE_URL}/locations/{location_without_state}/tides/latest"
        table = self.get_from_url(url)
        return table

    def extract_tides(self, location):
        """
        Scrape tide forecast web site.
        :param location: str
        :return: dict containing Tide instances
        """
        table = self.get_table(location)
        dates_from_table = self.get_dates_from_table(table)
        rise_and_set = self.get_rise_and_set(table)
        tides_for_location = self.get_tides(table, dates_from_table)

        filtered_tides = defaultdict(list)

        for indx, (dt, tide_data) in enumerate(tides_for_location.items()):
            for tide_time, value, units in tide_data:
                if rise_and_set[indx][0] <= tide_time <= rise_and_set[indx][1]:
                    filtered_tides[dt].append((tide_time, value, units))

        return filtered_tides

    def scrape(self):
        """
        Display extracted data for each location.
        :return: None
        """
        locations = (
            #'Half Moon Bay, California',
            #'Huntington Beach, California',
            #'Providence, Rhode Island',
            'Wrightsville Beach, North Carolina',
        )
        for location in locations:
            tides = self.extract_tides(location)
            print('Location:', location)
            for dt, tide_rows in tides.items():
                for tide_row in tide_rows:
                    print(dt, tide_row)


if __name__ == '__main__':
    scrape_tides = ScrapeTides()
    scrape_tides.scrape()
