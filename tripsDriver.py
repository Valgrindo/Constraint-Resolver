"""
A driver for the use of role restriction in pytrips.

:author: Jansen Orfan
"""

import pytrips.ontology as trips

lemma = "kill"
ont = trips.load()


ontTypes = ont.get_word(lemma) #possible classes/senses; don't use dictionary access via [], it seems to try looking for an ont type, then a sysnet 

for t in ontTypes:
	print("Type:",t)
	print("\tSynset:",t.words)
	print("\tSubsumed by:",t.parent)
	themeRoles = t.arguments #get thematic role objects
	print("\tRoles:")
	for r in themeRoles:
		print("\t\t:",r.role,"(",r.optionality,")")
		for res in r.getRawRestrictions(): #get any role restrictions, do not use r.restrictions this will not get the actual restrictions but I left it in case of compatibility issues
			print("\t\t\tRestriction Type", res[0],"\n\t\t\t\tValue:",res[1])
			
		

