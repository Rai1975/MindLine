import spacy

# Loading spacy model
nlp_model = spacy.load("en_core_web_sm")

# Function to get 
def get_doc_stats(doc):
    res = {}
    for token in doc:
        if token.pos_ not in res:
            res[token.pos_] = [token.text]
        
        else:
            res[token.pos_].append(token.text)
    
    return res

def find_noun_adj_pairs(doc, token, token_counter):
    candidates = []
    adjs = []
    start_token_number = token_counter
    end_token_number = token_counter
    curr_token = token

    if token.dep_ == "amod":
        candidates.append(token.head)
    
    elif token.dep_ == "acomp" or token.head.pos_ == "AUX":
        for child in token.head.children:
            if child.dep_ in ["nsubj", "attr"]:
                candidates.append(child)

    while curr_token.pos_ not in ['PUNCT', 'CCONJ'] and start_token_number > 0:
        start_token_number -= 1
        curr_token = doc[start_token_number]

    sub_token_range = doc[start_token_number:end_token_number]
    for sub_token in sub_token_range:
        if sub_token.pos_ in ["PROPN", "NOUN"]:
            candidates.append(sub_token)
            # adjectives.append((token.text, sub_token.text))
    
    # candidates.sort(key=lambda x: x.pos_ != "PROPN")

    conseq_nouns = find_conseq_nouns(doc)
    if candidates:
        if len(conseq_nouns) > 0:
            for n in conseq_nouns:
                candidates.append(n)
        for propn in candidates:
            adjs.append((propn.text, token.text))
        
    else:
        adjs = []

    return adjs

def consolidate_conj(doc, token, token_counter):
    candidates = []
    ads = []
    adjs = []
    start_token_number = token_counter
    end_token_number = token_counter
    curr_token = token

    ads.append(curr_token)

    # Traversing back thru the sentence, picking up adjectives until
    # noun/propn is found
    while token.text != '.' and start_token_number > 0:
        start_token_number -= 1
        curr_token = doc[start_token_number]

        if curr_token.pos_ in ["PROPN"]:
            break
    
    sub_token_range = doc[start_token_number:end_token_number]
    # print(sub_token_range)
    for sub_token in sub_token_range:
        if sub_token.pos_ in ["NOUN", "PROPN"]:
            candidates.append(sub_token)

        if sub_token.dep_ in ["amod", "acomp"]:
            ads.append(sub_token)
        
    # candidates.sort(key=lambda x: x.pos_ != "PROPN")
    # if candidates:
        # propn = candidates
    # else:
        # adjs = []
    
    conseq_nouns = find_conseq_nouns(doc)
    if len(conseq_nouns) > 0:
            for n in conseq_nouns:
                candidates.append(n)

    for noun in candidates:
        for adj in ads:
            adjs.append((noun.text, adj.text))
    
    return adjs

def find_conseq_nouns(doc):
    index = 0
    desired = ['PROPN', 'NOUN']
    conseq_nouns = []

    token = doc[0]
    while index < (len(doc) - 2) and token.nbor(1):
        if token.pos_ in desired:
            neighbors = [token.nbor(1), token.nbor(2)]
            if neighbors[0].pos_ in desired or neighbors[1].pos_ in desired:
                conseq_nouns.append(token)
                conseq_nouns.append(neighbors[0]) if neighbors[0].pos_ in desired else conseq_nouns.append(neighbors[1])
                token = token.nbor(2)
                index += 2
            else:
                token = token.nbor(1)
                index += 1 
        else:
            token.nbor(1)
            index += 1

    return list(set(conseq_nouns))

def analyze_sentence(sentence):
    adjectives = []
    doc = nlp_model(sentence)
    token_counter = 0

    # Search for adjectives
    for token in doc:
        # print(token.text, '-', token.pos_)
        if token.pos_ in ['ADJ']:
            if token.dep_ in ["amod", "acomp"]:
                pairs = find_noun_adj_pairs(doc, token, token_counter)
                for i in pairs:
                    adjectives.append(i)
            
            elif token.dep_ in ['conj']:
                pairs = consolidate_conj(doc, token, token_counter)
                for i in pairs:
                    adjectives.append(i)
                
        token_counter += 1

    final = list(set(adjectives))

    # Nouns without adjectives
    # what will we do for verbs that they like?
    # like cooking. etc.

    return final

if __name__ == "__main__":
    # sentences = ['Today felt really productive in a totally different way.', 'I finally got around to organizing my space, and the fact that everything in my space feels so much better when my things are clean and in order is crazy.', 'I even tried cooking something new, and the thing I cooked actually turned out pretty good, which surprised me.', 'Later on, I spent some time talking with a new coworker named Alex, and Alex and I just clicked right away—lots of laughs and easy conversation.', 'That day is one of those days where everything just flows, and I end it thinking, yeah...', 'this was a solid day.']

    sentence = 'Later on, I spent some time talking with a new coworker named Alex, and Alex and I just clicked right away—lots of laughs and easy conversation.'
    print(get_doc_stats(nlp_model(sentence)))
    print(analyze_sentence(sentence))

    # for sentence in sentences:
    #     print(analyze_sentence(sentence))
    #     print('---')
