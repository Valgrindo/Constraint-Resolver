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

from ontology_adapter import OntologyAdapter, Sense, Restriction

MAX_ID_RANGE = 1000


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

# A binding is an assignment of a type variable to a concrete sense
Binding = Tuple[T_Var, str]


class Resolver:
    """
    A collection of state and behaviors for a semantic resolver.
    """
    _T_VAR_ID = 0

    def __init__(self):
        self.relations = set()  # type: Set[Relation]
        self.senses = {}  # type: Dict[T_Var, List[Sense]]
        #  A mapping of (type var, sense) pairs to
        self.bindings = {}  # type: Dict[Binding, Dict[T_Var, List[str]]]

        self._adapter = OntologyAdapter()
        self._api = TripsAPI()

    def _reset(self) -> NoReturn:
        """
        Reset internal state.
        :return:
        """
        self.relations = set()
        self.senses = {}

    def resolve(self, sentence: str, mode: ResolveType, count: int = None):
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
        self._satisfy_constraints(mode)

        assignments = []
        # Create a set of annotated sentences using generated bindings.
        # The top level of the dictionary is the left hand side of binary relations.
        for key, matches in self.bindings.items():
            # The nested dictionary is the right hand side of binary relations.
            for t_var, senses in matches.items():
                # The list of senses is all the right-hand senses that make the relation valid for a set left-hand side.
                assignments.append((key, t_var, senses))

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
            self.senses[t_var] = senses

        # If this component has any children that represent concrete words, they form binary relations
        for cs in comp.roles[0].values():
            child = cs[0]

            # If the child AND this node represent a concrete word, form a binary relation.
            if not isinstance(child, str) and child.word and t_var:
                child_t_var = Resolver.get_tvar(child)
                self.relations.add((t_var, child_t_var))

            # Finally, recurse on the child
            self.__rel_rest_help(child)

    def _satisfy_constraints(self, mode: ResolveType) -> NoReturn:
        """
        Given a set of relations between type variables and a set of type variable senses/constraints, generate all
        satisfying assignments of senses.
        :param mode: strict or fuzzy matching
        :return:
        """
        # Algorithm is adapted from NLU by J. Allen, p.299
        if mode is ResolveType.FUZZY:
            raise NotImplementedError('Fuzzy matching not yet supported.')

        # For all relations in the sentence:
        for rel in self.relations:
            if not isinstance(rel, tuple):
                # No work needs to be done for unary relations, skip them.
                continue

            v1, v2 = rel  # Unpack the relation
            v1_senses, v2_senses = self.senses[v1], self.senses[v2]

            # The core of the problem is to find an assignment of senses for each binary relation such that
            # the selectional restrictions imposed by the sense of the first type var match the second type var
            # For each type var, senses that are not allowable are removed. If a type var is ever found to be with an
            # empty set of senses, the match is a failure.
            for sense in v1_senses:
                # The relation is valid if, for some sense s in v1 there exists a role r such that the restrictions on
                # r match the features of some sense s2 in v2
                for role in sense.roles.values():
                    # Examine all senses of v2 until we find something that fits this role
                    matches = list(filter(lambda s: self.matches_restrictions(s, role.restrictions), v2_senses))

                    # If the role is required and could not be matched up to a sense, then there is no valid
                    # interpretation.
                    if not role.optional and not matches:
                        options = "\n\t".join([s.name for s in v2_senses])
                        raise ValueError(f'Could not match required role {v1}.{sense.name}.{role.role} to any {v2} '
                                         f'sense:{options}')

                    # The above list contains the senses of v2 that can be paired with the current sense of v1
                    # Form Bindings out of all combinations of (v1, v2)
                    key = (v1, sense.name)
                    if key not in self.bindings:
                        self.bindings[key] = {}

                    if v2 not in self.bindings[key] and matches:
                        self.bindings[key][v2] = []
                    self.bindings[key][v2].extend([s.name for s in matches])

        # Once all relations have been examined, we have a complete set of allowable bindings.

    def matches_restrictions(self, s: Sense, rs: List[Restriction]) -> bool:
        """
        Test whether the given sense matches a provided list of restrictions.
        :param s: A Sense to match
        :param rs: Restrictions to match against
        :return: True if the Sense satisfies the Restrictions, False otherwise.
        """
        return True  # TODO: Implement

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
    for i in interpretations:
        print(i)


if __name__ == '__main__':
    main()
