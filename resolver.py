"""
Driver for a semantic ambiguity resolution program.

:author: Sergey Goldobin
:date: 07/06/2020
CS 799.06 Independent Study, RIT
"""

import argparse
import pytrips.ontology as ont
from enum import Enum
from trips_parser import TripsAPI
from logical_form import LogicalForm
from typing import *

from ontology_adapter import OntologyAdapter, Sense

MAX_ID_RANGE = 100


class ResolveType(Enum):
    """
    Operating modes for the resolver.
    """
    STRICT = "strict"
    FUZZY = "fuzzy"

    @staticmethod
    def parse(string: str):
        for t in ResolveType:
            if t.value == string:
                return t
        raise ValueError(f'Invalid ResolveType {string}')


# Type alias for type variables
T_Var = str

# Relations can be unary or binary
Relation = Union[T_Var, Tuple[T_Var, T_Var]]


class Resolver:
    """
    A collection of state and behaviors for a semantic resolver.
    """
    _T_VAR_ID = 0

    def __init__(self):
        self.relations = set()  # type: Set[Relation]
        self.senses = {}  # type: Dict[T_Var, List[Sense]]

        self._adapter = OntologyAdapter()
        self._api = TripsAPI()

    def _reset(self) -> NoReturn:
        """
        Reset internal state.
        :return:
        """
        self.relations = set()
        self.senses = {}

    def dump(self) -> str:
        """
        Return a text representation of the Resolver's contents.
        :return:
        """
        raise NotImplementedError("Resolver.dump()")
        # result = 'Type Variables:\n'
        # for t_var, senses in self.senses:
        #     #result += f'\t{}'
        #     pass

    def resolve(self, sentence: str, mode: ResolveType, count: int = None) -> List[str]:
        """
        Given a sentence, produce all valid semantic interpretations up to 'count'
        :param sentence: The sentence to resolve.
        :param mode: STRICT or FUZZY resolution.
        :param count: The number of interpretations to show.
        :return: A list of tagged interpretations.
        """
        self._reset()

        # The following steps are involved:
        # 1) Obtain a logical form of the sentence
        lf = self._api.parse(sentence)

        # 2) Obtain a set of unary and binary relations represented in the logical form
        self._get_relations_and_senses(lf)  # Stored in the Resolver's state

        # 3) Check the constraints imposed by those relations against the selectional restrictions. Discard any invalid
        # interpretations and store the valid ones.
        assignments = self._satisfy_constraints(mode)
        return assignments

    def _get_relations_and_senses(self, lf: LogicalForm):
        """
        Navigate a given logicalForm tree to obtain:
        1) A set of relations between all components of the tree represented as type variables.
        2) A mapping of type variables to all possible senses and corresponding restrictions.
        :param lf: A LogicalForm representation of a sentence.
        :return:
        """
        root = lf.get_tree()
        # The LF is a tree of Components connected by roles. Each component representing a word is a unary relation.
        # If a component representing a word has a child component filling a role slot that also represents a word, they
        # are in a binary relation.
        if root is None:
            return

        self.__rel_rest_help(root)

    def __rel_rest_help(self, comp):
        """
        Recursive helper function for relation and restriction search.
        :return:
        """
        # This is a leaf component with no word. Base case.
        if isinstance(comp, str) or (not comp.word and not comp.roles[0]):
            return

        t_var = None
        # If this component represents a word, create a unique type variable and a unary relation.
        if comp.word:
            t_var = Resolver.get_tvar(comp)
            self.relations.add(t_var)

            # Look up the senses and restrictions for this word
            senses = self._adapter.get_senses(comp.word[0])
            self.senses[comp.word[0]] = senses

        # If this component has any children that represent concrete words, they form binary relations
        for cs in comp.roles[0].values():
            child = cs[0]

            # If the child AND this node represent a concrete word, form a binary relation.
            if not isinstance(child, str) and child.word and t_var:
                child_t_var = Resolver.get_tvar(child)
                self.relations.add((t_var, child_t_var))

            # Finally, recurse on the child
            self.__rel_rest_help(child)

    def _satisfy_constraints(self, mode: ResolveType) -> List[str]:
        """
        Given a set of relations between type variables and a set of type variable senses/constraints, generate all
        satisfying assignments of senses.
        :param mode: strict or fuzzy matching
        :return:
        """
        raise NotImplementedError()

    @staticmethod
    def get_tvar(comp):
        """
        Get the name of a type variable from a component.
        :param comp:
        :return:
        """
        return f'{comp.word[0].upper()}_{hash(comp.comp_id) % MAX_ID_RANGE}'


def main():
    """
    The driver accepts a sentence as input and produces all valid semantic interpretations as output using a
    constraint satisfaction algorithm for semantic filtering.
    :return:
    """
    argp = argparse.ArgumentParser()
    argp.add_argument("sentence", help="Sentence to be resolved.")
    argp.add_argument("-m", "--mode", choices=[t.value for t in ResolveType], required=True, type=str,
                      help="Strictness of the algorithm.\n\tstrict\tRequires all semantic restrictions to match.\n"
                           "fuzzy\tAllows for some mismatch. Shows 'n' least mismatching interpretations.")
    argp.add_argument("-n", "--number", type=int, help="The number of interpretations to show. Required for fuzzy mode.")
    args = argp.parse_args()
    args.mode = ResolveType.parse(args.mode)  # The IDE warning is lying

    if args.number is None and args.mode == ResolveType.FUZZY:
        print(f'Argument -n is required for {ResolveType.FUZZY.value} mode.')
        exit(1)

    if args.number is not None:
        if args.number < 1:
            print(f'Argument -n cannot be less than 1.')
            exit(1)

    to_show = 'all' if args.number is None else args.number
    print(f'Resolving sentence: {args.sentence}\nMode: {args.mode.value}\n\nShowing {to_show} results:')

    resolver = Resolver()
    interpretations = resolver.resolve(args.sentence, args.mode, args.number)

    # Display all returned interpretations
    print('Interpretations:')
    for i in interpretations:
        print(i)



if __name__ == '__main__':
    main()
