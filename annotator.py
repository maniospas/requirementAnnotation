class Term:
    def __init__(self, text, start):
        self.generalized = False
        if start!=-1:
            if text.endswith("s") and not text[-2] in 'aeiou':
                text = text[:-1]
                self.generalized = True
            if text.startswith("non-"):
                text = text[4:]
                start += 4
            self.end = start+len(text)
        self.text = text
        self.start = start
        self.tag = None
    def to_text(self):
        if self.is_stopword():
            raise Exception("cannot convert stopword to text: "+self.text)
        return "T"+str(self.number)+"\t"+self.tag+" "+str(self.start)+" "+str(self.end)+"\t"+str(self.text)
    def is_stopword(self):
        return self.start==-1
    def list_self(self):
        return [self]
    def endswith(self, ending):
        return self.text.endswith(ending)
    def list_text(self):
        return [self.text]
    def equals(self, text):
        return self.text==text

class TermGroup:
    def __init__(self):
        self.terms = list()
        self.text = list()
        self.tag = None
        self.generalized = False
    def add(self, term):
        self.terms.append(term)
        self.text.append(term.text)
        if term.tag!=self.tag and not self.tag is None and not term.tag is None:
            raise Exception("Cannot add term to TermGroup with different tag")
        if not term.tag is None:
            self.tag = term.tag
        if term.generalized:
            self.generalized = True
    def empty(self):
        return len(self.terms)==0
    def is_stopword(self):
        return False
    def list_self(self):
        return self.terms
    def endswith(self, _):
        return False
    def list_text(self):
        return self.text
    def equals(self, _):
        return False

class Relation:
    def __init__(self, name, t1, t2):
        self.name = name
        self.t1 = t1
        self.t2 = t2
    def to_text(self):
        return "R"+str(self.number)+"\t"+self.name+" Arg1:T"+str(self.t1.number)+" Arg2:T"+str(self.t2.number)+"\t"

objects = list()#["account", "project", "entity", "relation", "list", "profile", "page", "systempath", "repository", "entities"]
properties = list()#"username", "password", "owner", "description", "name", "email", "description", "public", "anonymous", "source", "exists"]

def tag_line(line):
    line = [term for term in line]
    # remove language noise of consecutive stopwords
    pos = 1
    while pos<len(line):
        if line[pos].is_stopword() and line[pos-1].is_stopword():
            line.remove(line[pos])
        pos += 1
    # identify objects
    for pos, term in enumerate(line):
        if (term.generalized and (pos==0 or line[pos-1].tag!="Object")) or (pos>1 and line[pos-1].equals("the")) or (pos>1 and line[pos-1].equals("a")) or (pos>1 and line[pos-1].equals("an")) or term.endswith("ies"):
            if not term.text in objects and not term.is_stopword() and not term.text in properties:
                objects.append(term.text)
        if term.text in objects and (pos==0 or line[pos-1].tag!="Object" or line[pos-1].equals("the")):
            term.tag = "Object"
    # group terms
    groups = list()
    last_group = TermGroup()
    for pos, term in enumerate(line):
        if pos<len(line)-1 and line[pos+1].text in [",", "and", "or"] and not term.is_stopword():
            last_group.add(term)
            last_group.start_pos = pos
        elif not term.is_stopword():
            if(not last_group.empty()):
                last_group.add(term)
                last_group.end_pos = pos
                groups.append(last_group)
                last_group = TermGroup()
    for group in reversed(groups):
        line[group.end_pos] = group
        del line[group.start_pos:group.end_pos]
        
    # "Property for Text" -> "Text Property"
    for pos, term in enumerate(line):
        if term.equals("for") or term.equals("of"):
            if pos>=2 and (line[pos-2].equals("to") or line[pos-2].equals("can")):
                continue
            prev = line[pos-1]
            line.remove(prev)
            line.append(prev)
            prev.tag = None
    
    # remove stopwords
    relations = list()
    line_with_stopwords = line
    line = [term for term in line if not term.is_stopword()]
    
    # tag actor and action
    action = None
    for pos, term in enumerate(line):
        if term.equals("must") or term.equals("can"):
            if pos>=2:
                line[pos-2].tag = "Property"
                relations.append(Relation("HasProperty", line[pos-1], line[pos-2]))
            line[pos-1].tag = "Actor"
            line[pos+1].tag = "Action"
            action = line[pos+1]
            relations.append(Relation("IsActorOf", line[pos-1], line[pos+1]))
    # find all properties that follow after objects
    last_object = None
    for term in line:
        if term.equals("must") or term.equals("can"):
            last_object = None
        elif term.tag=="Object":
            last_object = term
        elif term.tag is None and not last_object is None:
            term.tag = "Property"
            relations.append(Relation("HasProperty", last_object, term))
            last_object = None
    prev_property = None
    for term in line:
        if term.text=="must" or term.text=="can":
            prev_property = None
        elif term.tag=="Object" and not prev_property is None:
            prev_property.tag = "Property"
            relations.append(Relation("HasProperty", prev_property, term))
            prev_property = None
        elif term.tag is None and not term.is_stopword():
            prev_property = term
                   
    # "Text Property" where "Text" is an object should mean that "Property" is its property
    line = line_with_stopwords
    for pos, term in enumerate(line):
        if term.tag=="Object":
            if pos<len(line)-1 and not line[pos+1].tag=="Object" and not line[pos+1].is_stopword():
                if line[pos+1].tag is None:
                    line[pos+1].tag = "Property"
                    relations.append(Relation("HasProperty", term, line[pos+1]))
                relations.append(Relation("ActsOn", action, line[pos+1]))
            else:
                relations.append(Relation("ActsOn", action, term))
    
    print([str(term.text) for term in line])
    print([term.tag+" : "+str(term.text) for term in line if not term.tag is None])
    # parse back group info to its members
    for group in groups:
        for term in group.terms:
            term.tag = group.tag
    correct_relations = list()
    for relation in relations:
        for t1 in relation.t1.list_self():
            for t2 in relation.t2.list_self():
                correct_relations.append(Relation(relation.name, t1, t2))
    #
    return correct_relations
        
def get_term_lines(path):
    with open(path, 'r') as file:
        lines = list()
        line_start = 0
        for line in file:
            lines.append((line, line_start))
            line_start += len(line)
        
    term_lines = list()
    from nltk.corpus import stopwords
    #from nltk.tokenize import word_tokenize  
    stopwords = set(stopwords.words('english'))
    stopwords.add("able")
    stopwords.add("other")
    stopwords.add("another")
    stopwords.add("whether")
    stopwords.add(",")
    for text, position in lines:
        term_line = list()
        text = text.lower()
        words = [word for word in text[0:-1].replace(",", " ,").split(" ")]
        for word in words:
            if word in stopwords:
                term_line.append(Term(word,-1))
            if word not in [term.text for term in term_line]:
                term_line.append(Term(word, text.find(word)+position))
        #print([term.text for term in term_line])
        term_lines.append(term_line)
    return term_lines
        
term_lines = get_term_lines("EntityDatabase.txt")
term_number = 1
relation_number = 1
processed_lines = list()
for line in term_lines:
    relations = tag_line(line)
    processed_line = [term for term in line if not term.tag is None]
    for term in processed_line:
        term.number = term_number
        term_number += 1
    for relation in relations:
        relation.number = relation_number
        relation_number += 1
    processed_line.extend(relations)
    processed_lines.append(processed_line)

with open("EntityDatabase.ann", 'w') as file:
    number = 0
    for line in processed_lines:
        for term in line:
            file.write(term.to_text()+"\n")