"""
An interface for TRIPS Web API.

:author: Sergey Goldobin
:date: 06/09/2020
"""

import requests
import argparse

from logical_form import LogicalForm


class TripsAPI:
    """
    A wrapper interface to communicate with the web TRIPS API.
    """

    _URL = "http://trips.ihmc.us/parser/cgi/parse"

    @staticmethod
    def parse(sentence: str) -> LogicalForm:
        """
        Convert a sentence to Logical Form.
        :param sentence: A recognized sentence string.
        :return: A LogicalForm instance.
        """
        # TODO: This is a decision point. Sometime later I need to determine if I'll be doing any cleaning to the
        # sentence (which just came out of Google Speech), or if I'm using it "as is".
        post_data = {"input": sentence}
        reply = None

        try:
            reply = requests.post(TripsAPI._URL, post_data)
        except Exception as e:
            print(f'There was an error processing a web request: {e}')
            return LogicalForm(None)

        xml_str = reply.text
        return LogicalForm(xml_str)


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("text", help="Text to be semantically parsed.")
    args = arg_parser.parse_args()

    print(f'Parsing into AMR:\t{args.text}')
    api = TripsAPI()
    lf = api.parse(args.text)

    print(lf.pretty_format())

