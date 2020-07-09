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

from ontology_adapter import OntologyAdapter, Sense, Restriction, RestrictionType

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

# An assignment of one type var with all corresponding matching assignments of another.
Assignment = Tuple[Binding, T_Var, List[str]]


class Resolver:
    """
    A collection of state and behaviors for a semantic resolver.
    """

    def __init__(self):
        self.relations = set()  # type: Set[Relation]
        self.senses = {}  # type: Dict[T_Var, List[Sense]]
        #  A mapping of (type var, sense) pairs to
        self.bindings = {}  # type: Dict[Binding, Dict[str, List[Binding]]]
        self.__seen_components = set()

        self._adapter = OntologyAdapter()
        self._api = TripsAPI()

    def _reset(self) -> NoReturn:
        """
        Reset internal state.
        :return:
        """
        self.relations = set()
        self.senses = {}
        self.__seen_components = set()

    def resolve(self, sentence: str, mode: ResolveType, count: int = None):
        """
        Given a sentence, produce all valid semantic interpretations up to 'count'
        :param sentence: The sentence to resolve.
        :param mode: STRICT or FUZZY resolution.
        :param count: The number of interpretations to show.
        :return: A list of assignments and a success indicator.
        """
        self._reset()

        # The following steps are involved:
        # 1) Obtain a logical form of the sentence
        lf = self._api.parse(sentence)

        # 2) Obtain a set of unary and binary relations represented in the logical form
        self._get_relations_and_senses(lf)  # Stored in the Resolver's state
        for t_var, senses in self.senses.items():
            if not senses:
                print(f'No senses found for {t_var}')

        # 3) Check the constraints imposed by those relations against the selectional restrictions. Discard any invalid
        # interpretations and store the valid ones.
        bad_roles = self._satisfy_constraints(mode)

        return self.bindings, bad_roles

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

        if comp in self.__seen_components:
            return
        self.__seen_components.add(comp)

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

    def _satisfy_constraints(self, mode: ResolveType) -> Set[Tuple[Binding, str]]:
        """
        Given a set of relations between type variables and a set of type variable senses/constraints, generate all
        satisfying assignments of senses.
        :param mode: strict or fuzzy matching
        :return:
        """
        # Algorithm is adapted from NLU by J. Allen, p.299
        if mode is ResolveType.FUZZY:
            raise NotImplementedError('Fuzzy matching not yet supported.')

        # Relations must be considered in groups of matching left-hand side
        # For example, if there are relations (V1, V2), (V1, V3), (V1, V4), then a satisfactory assignment is one where
        # All required and any optional roles of V1 are occupied by some combination of V2, V3, and V4
        groups = {}
        unsatisfied_roles = set()
        for rel in self.relations:
            if not isinstance(rel, tuple):
                continue
            v1, v2 = rel
            if v1 not in groups:
                groups[v1] = []
            groups[v1].append(v2)

        for parent, children in groups.items():
            # We must find all combinations of children that fill required slots on the parent.
            p_senses = self.senses[parent]

            # For every sense of the parent
            for p_sense in p_senses:
                # Gather all roles with specific restrictions
                relevant_roles = list(filter(lambda r: r.is_specific(), p_sense.roles.values()))
                key = (parent, p_sense.name)
                if key not in self.bindings:
                    self.bindings[key] = {}

                # For every role with restrictions on the parent
                for r in relevant_roles:
                    # For every right-hand-side child
                    fitting_children = []
                    for c in children:
                        c_senses = self.senses[c]
                        # Get all the child's senses that fit the role
                        matches = list(filter(lambda s: self.matches_restrictions(s, r.restrictions), c_senses))
                        fitting_children.extend((c, s.name) for s in matches)

                    if not r.optional and not fitting_children:
                        unsatisfied_roles.add((key, r.role))

                    if r.role not in self.bindings[key]:
                        self.bindings[key][r.role] = []
                    self.bindings[(parent, p_sense.name)][r.role].extend(fitting_children)

                # There were no wildcard or required roles on a sense and all of them are unsatisfied, then so is the
                # sense
                if len(self.bindings[(parent, p_sense.name)]) == len(p_sense.roles):
                    if all(not matches for _, matches in self.bindings[(parent, p_sense.name)].items()):
                        unsatisfied_roles.add(((parent, p_sense.name), 'ALL'))

        # Once all relations have been examined, we have a complete set of allowable bindings.
        return unsatisfied_roles

    @staticmethod
    def matches_restrictions(s: Sense, rs: List[Restriction]) -> bool:
        """
        Test whether the given sense matches a provided list of restrictions.
        :param s: A Sense to match
        :param rs: Restrictions to match against
        :return: True if the Sense satisfies the Restrictions, False otherwise.
        """
        # The sense matches restrictions if every individual restriction is satisfied.
        for r in rs:
            if r.type in [RestrictionType.TYPE, RestrictionType.TYPEQ]:
                # The type of this sense must match at least one within the restriction list.
                # The type does not have to match exactly. A matching ancestor is acceptable.
                # For example, if the restriction calls for a phys-obj and the sense is a car, it passes.

                # Trips uses a 'type' constant to indicate a wildcard, matching anything
                if r.wildcard:
                    continue

                anc_overlap = list(filter(lambda x: x in r.values, s.ancestry))
                if (s.name not in r.values) and (not anc_overlap):
                    # Neither this sense nor its ancestry matched up to the restriction.
                    return False
            elif r.type is RestrictionType.FEATURES:
                # The set of features represented in the restriction must be a proper subset of sense features.
                for f_name, f_val in r.values:
                    if not isinstance(f_val, str):
                        continue
                    if f_name not in s.features:
                        # A required feature is missing
                        return False
                    if s.features[f_name].lower() != f_val.lower():
                        # Value mismatch for required feature.
                        return False

        # Made it to the end with no failures ==> Match
        return True

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
    args = argp.parse_args()
    args.mode = ResolveType.parse(args.mode)  # The IDE warning is lying

    print(f'Resolving sentence: {args.sentence}\nMode: {args.mode.value}')

    resolver = Resolver()
    bindings, errors = resolver.resolve(args.sentence, args.mode)

    if errors:
        print('Failed to find a satisfying assignment for the following senses:')
        for e in errors:
            print(e)
            # Remove invalid senses from the result set
            del bindings[e[0]]

    print('\nSatisfying bindings:')
    # Display all returned bindings
    for binding, roles in bindings.items():
        print(binding)
        impossible_roles = []
        for role, assignments in roles.items():
            if not assignments:
                impossible_roles.append(role)
            else:
                print(f'\t{role} -> [{", ".join([f"({a[0]}, {a[1]})" for a in assignments])}]')
        if impossible_roles:
            print(f'\tUnsatisfiable roles: {impossible_roles}')
        print(f'\tANY sense of other components for all other roles')


if __name__ == '__main__':
    main()
