"""
A wrapper for pyTrips ontology browser.

:author: Sergey Goldobin
:date: 07/07/2020
"""

from typing import *
import pytrips.ontology as trips
from dataclasses import dataclass
from enum import Enum


class RestrictionType(Enum):
    """
    Different types of restrictions that can exist.
    """
    TYPE = 'type'
    TYPEQ = 'typeq'
    DEFAULTS = 'defaults'
    FEATURES = 'features'

    @staticmethod
    def from_string(string: str):
        for t in RestrictionType:
            if t.value == string:
                return t
        raise ValueError(f'Invalid RestrictionType {string}')


@dataclass
class Restriction:
    type: RestrictionType
    values: List[Union[str, Tuple[str, ...]]]

    def parse(self, string: str):
        """

        :param string:
        :return:
        """
        pass


@dataclass
class Role:
    """
    A role has a name and a set of restrictions, as well as an optionality
    """
    role: str
    optional: bool
    restrictions: List[Restriction]


@dataclass
class Sense:
    """
    A word sense is a name combined with a collection of roles and restrictions
    """
    name: str
    roles: Dict[str, Role]

    def __repr__(self):
        return f'Sense(name="{self.name}")'


class OntologyAdapter:

    def __init__(self):
        """
        Initialize the adapter.
        """
        self._ont = trips.load()

    def get_senses(self, word: str) -> List[Sense]:
        """
        Given a word, fetch a collection of its Senses
        :param word: The word to look up in the ontology.
        :return: A list of the word's Senses
        """
        ont_types = self._ont.get_word(word)
        senses = []

        for t in ont_types:
            name = str(t)
            roles = {}

            for r in t.arguments:
                role = r.role
                optional = r.optionality

                restrictions = []
                for raw in r.getRawRestrictions():
                    rest = Restriction(type=RestrictionType.from_string(raw[0]), values=raw[1])
                    restrictions.append(rest)

                roles[role] = Role(role, optional, restrictions)

            sense = Sense(name, roles)
            senses.append(sense)

        return senses

