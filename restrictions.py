class TripsRestriction(object):
    def __init__(self, role, restrs, optionality, ont):
        self.__ont = ont
        self.__role = role
        self.__restrs = set()
        for x in restrs:

            if type(restrs) is dict: #bug fix, I'm not sure if this will ever be false but keep the else cases to be safe

                if type(restrs[x]) is list:
                   value = []
                   for v in restrs[x]:  #build tuple of lowercase restrictions to preserve format
                       value.append(TripsRestriction.formatListValues(v))
                   value = tuple(value)
                else:
                    value = restrs[x].lower()

                self.__restrs.add( (x.lower(),value) )  #adding restrictions as ordered pair (restriction-type, value)
            else:    
                if type(x) is list:
                    self.__restrs.update(x[2:])
                if type(x) is str:
                    self.__restrs.add(x)


        if type(restrs) is dict: #ditto
            pass
        else:        
            self.__restrs = {x.lower() for x in self.__restrs}

        self.__optionality = optionality
        
    def formatListValues(l): #bugFix helper
       ret = []
       if type(l) is list:
               for v in l:
                   ret.append(TripsRestriction.formatListValues(v))
       else:
           return l.lower()
       return tuple(ret)
    @property
    def role(self):
        return self.__role.lower()

    @property
    def restrictions(self):
        return [x for x in [self.__ont[r] for r in self.__restrs] if x]

    def getRawRestrictions(self): #use this instead
    	return self.__restrs

    @property
    def optionality(self):
        return self.__optionality

    def __str__(self):
        return "[:%s %s]".format(self.role, ", ".join(self.restrictions))

    def __repr__(self):
        res = ""
        if self.restrictions:
            res = self.restrictions[0]
        post = ""
        if len(self.restrictions) > 1:
            post = "and {} others".format(len(self.restrictions)-1)
        return "<TripsRestriction :{} {}{}>".format(self.role, res, post)
