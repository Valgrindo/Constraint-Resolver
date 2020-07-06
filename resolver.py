"""
Driver for a semantic ambiguity resolution program.

:author: Sergey Goldobin
:date: 07/06/2020
CS 799.06 Independent Study, RIT
"""

import argparse
import pytrips
from parser import TripsAPI
from logical_form import LogicalForm


STRICT = "strict"
FUZZY = "fuzzy"


def main():
    """
    The driver accepts a sentence as input and produces all valid semantic interpretations as output using a
    constraint satisfaction algorithm for semantic filtering.
    :return:
    """
    argp = argparse.ArgumentParser()
    argp.add_argument("sentence", help="Sentence to be resolved.")
    argp.add_argument("-m", "--mode", choices=[STRICT, FUZZY], required=True,
                      help="Strictness of the algorithm.\n\tstrict\tRequires all semantic restrictions to match.\n"
                           "fuzzy\tAllows for some mismatch. Shows 'n' least mismatching interpretations.")
    argp.add_argument("-n", "--number", type=int, help="The number of interpretations to show. Required for fuzzy mode.")
    args = argp.parse_args()

    if args.number is None and args.mode == FUZZY:
        print(f'Argument -n is required for {FUZZY} mode.')
        exit(1)

    if args.number is not None:
        if args.number < 1:
            print(f'Argument -n cannot be less than 1.')
            exit(1)

    to_show = 'all' if args.number is None else args.number
    print(f'Resolving sentence: {args.sentence}\nMode: {args.mode}\n\nShowing {to_show} results:')

    # The following steps are involved:
    # 1) Obtain a logical form of the sentence
    api = TripsAPI()
    lf = api.parse(args.sentence)

    # 2) Obtain a set of unary and binary relations represented in the logical form
    relations, restrictions = get_relations_and_restrictions(lf)

    # 3) Check the constraints imposed by those relations against the selectional restrictions. Discard any invalid
    # interpretations and store the valid ones.
    assignments = satisfy_constraints(relations, restrictions, args.mode)

    # 4) Display N valid ones discovered.
    

def get_relations_and_restrictions(lf: LogicalForm):
    """
    Navigate a given logicalForm tree to obtain:
    1) A set of relations between all components of the tree represented as type variables.
    2) A mapping of type variables to all possible senses and corresponding restrictions.
    :param lf: A LogicalForm representation of a sentence.
    :return:
    """
    root = lf.get_tree()
    raise NotImplementedError()


def satisfy_constraints(relations, restrictions, mode):
    """
    Given a set of relations between type variables and a set of type variable senses/constraints, generate all
    satisfying assignments of senses.
    :param relations: A set of unary and/or binary relations between type variables.
    :param restrictions: A mapping of type variables to their senses and restrictions
    :param mode: strict or fuzzy matching
    :return:
    """
    raise NotImplementedError()


if __name__ == '__main__':
    main()
