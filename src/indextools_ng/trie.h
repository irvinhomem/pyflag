/*****************************************
   This file implements a trie.

  A Trie is a special data structure with multiple elements under each
  node.
***********************************/
#ifndef __TRIE_H
#define __TRIE_H

#include <Python.h>
#include "class.h"
#include "list.h"
#include <stdint.h>

/** These are the possible types that words may be supplied as **/
enum word_types {
  // This is a literal
  WORD_LITERAL,

  // This is an extended format (regex like) 
  WORD_EXTENDED,

  // This is an english word (case insensitive matching)
  WORD_ENGLISH
};

/** This is an abstract class with no constructors, it must be
    extended.
*/
CLASS(TrieNode, Object)
     struct list_head peers;

     /** This points to a dummy TrieNode object which serves as a
	 list_head for the peers list of all this nodes children 
     */
     TrieNode child;

     /** Checks if there is a match at the current position in buffer. 
	 May alter result with the value stored in the node.
     */
     int METHOD(TrieNode, Match, char **buffer, int *len, PyObject *result);

     /** Adds the word into the trie with the value in data */
     void METHOD(TrieNode, AddWord, char **word, int *len, long int data,
		 enum word_types type);

     int METHOD(TrieNode, __eq__, TrieNode tested);

/** This is a simple constructor. It is mostly used for creating list
    heads for children */
     TrieNode METHOD(TrieNode, Con);
END_CLASS

CLASS(DataNode, TrieNode)
     int data;

     DataNode METHOD(DataNode, Con, int data);
END_CLASS

CLASS(LiteralNode, TrieNode)
     char value;

     LiteralNode METHOD(LiteralNode, Con, char **value, int *len);
END_CLASS

CLASS(RootNode, TrieNode)
  
     RootNode METHOD(RootNode, Con);
END_CLASS

CLASS(CharacterClassNode, TrieNode)
     char *map;
     CharacterClassNode METHOD(CharacterClassNode, Con, char **word, int *len);
END_CLASS

#endif