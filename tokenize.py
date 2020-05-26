#This simple app Tokenizes SQL, specifically Postgresql to identify tables for common syntax. Could be adapted to demo 
# Tokenization of any text string.

import os

KEYWORD, KOI, IDENTIFIER, OPERATOR, SPECIAL_CHARACTER, CONSTANT, UNKNOWN, EOF, SOF = 'KEYWORD', 'KOI', 'IDENTIFIER', 'OPERATOR', 'SPECIAL_CHARACTER', 'CONSTANT', 'UNKNOWN', 'EOF', 'SOF'

#special characters found in sql include: 
spec_char = {'$', '[', ']', '(', ')', ',', ':', ';', '*'}
dot = '.'

#operators in sql include:
#These can be replaced with any key word or word of interest in a syntax tree
oper = {'+', '-', '*', '/', '<', '>', '=', '~', '!', '@', '%', '^', '&', '|', '`', '?'}
key_of_inter = {'into', 'with', 'alter', 'table', 'drop', 'into', 'join', 'from', 'into' }
keyword_name = {'select', 'insert', 'delete', 'update', 'create', 'drop', 'alter', 'on', 'where', 'group', 'by', 'left', 'right', 'normal', 'outer', 'having', 'order', 'values', 'EOF', '(', ')', 'as'}
keyword_identifier = {'a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N','O','P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '_' }
numbers = {'1','2','3','4','5','6','7','8','9','0', '.'}
number ={1,2,3,4,5,6,7,8,9,0}
identifier_alphanum = keyword_identifier | {'$','\"', '*'} | numbers 
constant = {'\'', '$',  } #TODO: add bitstring
quoted_identifier = '"'

whitespace = {' ', '\t', '\n', '\r', '\r\n'}

class Token:
    def __init__(self,type, value):
        self.value = value
        self.type = type
    
    def __str__(self):
        ret = 'Token({type}, {value})'.format(type = self.type, value = repr(self.value))
        return ret
    
    def __repr__(self):
        return self.__str__()

class Tokenize:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos]
        self.current_token = None
        self.token_list = []

    def error(self):
        raise Exception('Invalid Syntax')

    def get_next_char(self):    
        self.pos += 1
        if self.pos > len(self.text) - 1:
            self.current_char = None
        else:
            self.current_char = self.text[self.pos]
    
    def get_next_non_whitespace(self):
        while self.current_char is not None and self.current_char in whitespace:
            self.get_next_char()
    
    def get_number(self):
        num = ''
        if self.current_char == '\'':
            num += self.current_char
            self.get_next_char()
            while self.current_char is not None and self.current_char is not '\'':                            
                num += self.current_char                
                self.get_next_char()                
            num += self.current_char
            self.get_next_char()
        else:
            while self.current_char is not None and self.current_char not in whitespace:
                num += self.current_char
                self.get_next_char()
        return num
    
    def get_operator(self):
        op = ''
        while self.current_char in oper:
            op += self.current_char
            self.get_next_char()
        return op
    
    def get_special_character(self):
        sc = ''
        while self.current_char is not None and self.current_char in spec_char:
            sc += self.current_char
            self.get_next_char()
        return sc
    
    def get_word(self):
        word = ''
        while self.current_char is not None and self.current_char in identifier_alphanum:
            word += self.current_char
            self.get_next_char()  
        return word
    
    def get_constant(self):
        constant = ''
        while self.current_char is not None:
            constant += self.current_char
            self.get_next_char()
        return constant
    
    def get_token_list(self):
        self.current_token = self.get_next_token()
        while self.current_token.type is not EOF:
            self.token_list.append(self.current_token)
            self.current_token = self.get_next_token()
        self.token_list.append(self.current_token)
        
        return self.token_list
    
    def get_next_token(self):

        if self.current_char in whitespace:
            self.get_next_non_whitespace()
        
        if self.current_char == None:
            return Token(EOF, None)
        
        elif self.current_char in oper:
            op = self.get_operator()
            return Token(OPERATOR, op)
        
        elif self.current_char in spec_char:
            sc = self.get_special_character()
            return Token(SPECIAL_CHARACTER, sc)
        
        elif self.current_char.isdigit() or self.current_char in constant or self.current_char == dot:
            num = self.get_number()
            return Token(CONSTANT, num)
        
        elif self.current_char in keyword_identifier or self.current_char == quoted_identifier:
            word = self.get_word().lower()
            if word in key_of_inter:
                return Token(KOI, word)
            elif word in keyword_name: 
                return Token(KEYWORD, word)
            else:
                return Token(IDENTIFIER, word)  
        else:
            self.error()

class Parse:
    def __init__(self, token_list):
        self.token_list = token_list
        self.token_list.insert(0,Token(SOF, None))
        self.pos = 0
        self.current_token = self.token_list[self.pos]
        self.next_token = token_list[self.pos + 1]
        self.previous_token = None
        self.expression_list = []
        self.in_koi = False
    
    def __str__(self):
        ret = 'Tokens: {length}'.format(len(self.token_list))
        return ret
    
    def __repr__(self):
        return self.__str__()
    
    def build_expression(self):
        #schema . table . column
        self.in_koi = True
        # print('Start KOI: ', self.current_token.value)
        ret = []
        while self.current_token.type is not EOF and self.current_token.value not in keyword_name:
            ret.append(self.current_token)              
            self.get_next_token()     

        self.in_koi = False
        # print('End KOI: ', self.current_token.value)       
        self.expression_list.append(ret)

    def get_expressions(self):
        while self.current_token.type is not EOF:            
            self.get_next_token()
            if self.current_token.type is KOI:
                self.build_expression()
            
        return self.expression_list
    
    def get_next_token(self):
        self.previous_token = self.current_token
        self.pos += 1
        self.current_token = self.token_list[self.pos]
        if self.current_token.type is not EOF:
            self.next_token = self.token_list[self.pos + 1]
        else:
            self.next_token = Token(EOF, None)

def Main():
    while True:
        try:
            text = input('folder location> ')
            for f in os.scandir(text):                
                with open(f,'r') as fn:
                    print('\nFILE NAME: ', fn.name, '\n')
                    fnr = fn.read()
                    parse_folder(fnr)
                
            #parse_folder('SELECT A.col1, B.col1, B.col3, C.col1 FROM table1 as "A" LEFT OUTER JOIN table2 as B ON A.col1 = B.col1 INNER JOIN table3 as C ON A.col1 = C.col1 AND B.col1 = C.col1 WHERE col1 = col2')
        except EOFError:
            break

def parse_folder(text):
    tokenize = Tokenize(text)
    lst = tokenize.get_token_list()
    # for t in lst:
    #     print(t)
    parse_it = Parse(lst)
    p_lst = parse_it.get_expressions()
    for u in p_lst:
        print(u)
       
if __name__ == '__main__':
    Main()

