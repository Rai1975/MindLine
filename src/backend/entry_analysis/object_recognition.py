import spacy

# Loading spacy model
nlp_model = spacy.load("en_core_web_sm")
# Entities spaCy considers "significant" for emotional context
SIGNIFICANT_ENT_TYPES = {"PERSON", "ORG", "GPE", "EVENT", "WORK_OF_ART"}

FILLER_NOUNS = {
    "thing", "things", "something", "anything", "everything",
    "time", "way", "fact", "lot", "day", "kind", "sort",
    "people", "person", "place"
}

def is_significant_token(token):
    """
    Returns True if a noun/propn is worth pairing with an adjective.
    Priority: named entities > grammatical subjects/objects > everything else
    """
    # 1. Named entity — most reliable signal for "person or place"
    if token.ent_type_ in SIGNIFICANT_ENT_TYPES:
        return True

    # 2. Grammatical subject or object — the actor/receiver in the sentence
    if token.dep_ in ("nsubj", "nsubjpass", "dobj", "pobj"):
        # But skip generic fillers like "thing", "way", "fact"
        if token.lemma_.lower() not in FILLER_NOUNS:
            return True

    # 3. Proper nouns are almost always significant (names, places)
    if token.pos_ == "PROPN":
        return True

    return False

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
    curr_token = token

    # --- Dependency-based pairing (preferred, most accurate) ---
    if token.dep_ == "amod":
        if is_significant_token(token.head):          # ← filter here
            candidates.append(token.head)
    
    elif token.dep_ in ("acomp", "attr") or token.head.pos_ == "AUX":
        for child in token.head.children:
            if child.dep_ in ("nsubj", "attr") and is_significant_token(child):
                candidates.append(child)

    # --- Proximity scan fallback (only if dep tree gave nothing) ---
    if not candidates:
        while curr_token.pos_ not in ['PUNCT', 'CCONJ'] and start_token_number > 0:
            start_token_number -= 1
            curr_token = doc[start_token_number]

        for sub_token in doc[start_token_number:token_counter]:
            if sub_token.pos_ in ("PROPN", "NOUN") and is_significant_token(sub_token):
                candidates.append(sub_token)

    # --- Consecutive noun check (also filtered) ---
    for n in find_conseq_nouns(doc):
        if is_significant_token(n):
            candidates.append(n)

    candidates = list(set(candidates))  # dedupe

    for propn in candidates:
        adjs.append((propn.text, token.text))

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
            n1_sig = neighbors[0].pos_ in desired and is_significant_token(neighbors[0])
            n2_sig = neighbors[1].pos_ in desired and is_significant_token(neighbors[1])

            if n1_sig or n2_sig:
                if is_significant_token(token):
                    next_tok = neighbors[0] if n1_sig else neighbors[1]
                    if token.pos_ == "NOUN" and next_tok.pos_ == "PROPN":
                        pass  # drop "friend", keep "Jacob"
                    else:
                        conseq_nouns.append(token)

                if n1_sig:
                    conseq_nouns.append(neighbors[0])
                elif n2_sig:
                    conseq_nouns.append(neighbors[1])
                token = token.nbor(2)
                index += 2
            else:
                token = token.nbor(1)
                index += 1
        else:
            index += 1
            if index < len(doc):
                token = doc[index]

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

# if __name__ == "__main__":
    # sentences = ['Today felt really productive in a totally different way.', 'I finally got around to organizing my space, and the fact that everything in my space feels so much better when my things are clean and in order is crazy.', 'I even tried cooking something new, and the thing I cooked actually turned out pretty good, which surprised me.', 'Later on, I spent some time talking with a new coworker named Alex, and Alex and I just clicked right away—lots of laughs and easy conversation.', 'That day is one of those days where everything just flows, and I end it thinking, yeah...', 'this was a solid day.']

    # sentence = 'Later on, I spent some time talking with a new coworker named Alex, and Alex and I just clicked right away—lots of laughs and easy conversation.'
    # print(get_doc_stats(nlp_model(sentence)))
    # print(analyze_sentence(sentence))

    # for sentence in sentences:
    #     print(analyze_sentence(sentence))
    #     print('---')
