% #############################################################################
% Thesis-MSc
% Version 5.0, October, 14 2025
% BY: Prof. Rui Santos Cruz, rui.s.cruz@tecnico.ulisboa.pt
% #############################################################################

The Thesis-MSC LaTeX template can be used for Instituto Superior Técnico 
Master of Science dissertation, as it follows the regulations published 
by the Scientific Council of IST.
The current version of the Guide, as of 2025 is available at: 
https://tecnico.ulisboa.pt/files/2021/09/guia-disserta-o-mestrado.pdf

The template is prepared for writing the dissertation in either Portuguese or English.
The language selection is made as specified here.
The language selection will prepare the core structure of the document, not the "content"

You may modify parameters or include other LaTeX packages if deemed necessary,
invoking them in the preamble (Preamble_commands.tex).

To start using the template, just open and modify your data in the following files:
=====================================================================================
1. Preamble_commands.tex
=====================================================================================
Select the ‘main’ language of your thesis in the line that loads the package ‘babel’:
line.20
	\usepackage[main=english,portuguese]{babel}	% for ENGLISH
	or 
	\usepackage[english,main=portuguese]{babel} % fot PORTUGUESE
	
The document will then "auto-magically" modify all the adequate keywords, titles, 
captions, etc. according to the selected language.
=====================================================================================
To deliver a PDF version without annotations/todonotes and Track Changes,
you need to modify the options as follows:

For TODO Notes, the following lines:
line.105/106
    % To ENABLE, select the following line:
    \usepackage[textwidth=2cm, textsize=small]{todonotes}
    % To DISABLE, select the line with the 'disable' option:
    \usepackage[textwidth=2cm, textsize=small, disable]{todonotes}
 
For Track Changes, the following lines: 
line.113/114
    % To supress displaying track changes, use the line with the 'final' option
    \usepackage[authormarkup=superscript,authormarkuptext=id,markup=underlined,ulem={ULforem,normalbf},final]{changes}

=====================================================================================
2. Front_Cover.tex
=====================================================================================
In this document insert your data (your full name, dissertation titles, 
supervisors names, date, degree, etc.) in the following fields:

	\title{}
	\subtitle{}
	\author{}
	\degree{}
	\supervisor{}
	\othersupervisor{}
	\date{}

Staring at line 36 you can select /or change) the official name of the course/degree. 
Please chose portuguese or english line, depending if the document is written 
in portuguese or in english, respectiveley.

For using Tracking Changes, you can also replace the id of the collaborators, in the lines 64-66:

    \definechangesauthor[color=colorname]{id}

For a DRAFT version of the thesis (before examination) select (comment/uncomment) 
the following line with the value ‘false’ (in lines 72/73):

	\finalthesis{false}

For the final version (approved after examination) then select (comment/uncomment) 
the following line with the value ‘true’ (in lines 72/73):

	\finalthesis{true}

and include the full names of all the members of the Examination Committee (except the Supervisor), as officially approved:

	\chairperson{} (the President of the Committee, after approval)
	\vogalone{} (it is, normally, the only committee member, i.e., the main Examiner)
	\vogaltwo{} (normally not used)
	\vogalthree{} (normally not used)
=====================================================================================
3. The Content
=====================================================================================
The content of your thesis will be written in the documents that are in folder ‘Chapters’.
Do not modify the ‘header’ in all those documents, except the title of 
each document as the ‘header’ contains compilation directives.
 
If you need to add more Chapters, just create new .tex documents and add the header.

The Chapters in your dissetrtation, are defined in the lines 150 and following 
in the main document:

  	‘Main_Document.tex’

For example, if you do not need a 6th Chapter, comment the lines starting at 184:

	%Chapter 6
	\input{./Chapters/Chapter_6.tex}
	% If Printing on DOUBLE SIDED pages, the second page should be white.
	% Otherwise, comment the following command:
	\cleardoublepage

=====================================================================================
4. Bibliography.bib
=====================================================================================
This file is the default Bibliography database. 
If you are using some Reference Manager, such as Zotero [zotero.org], or Bibdesk, 
you can export your Library into a "Bibtex" .bib file.
You may then opt for one of these methods:
a. replace the content of Bibliography.bib with the content of the exported file
    (generated by the Reference Manager).
b. upload the the exported file (generated by the Reference Manager) and modify 
    the corresponding line (215) in the main document ‘Main_Document.tex’ to reflect 
    the filename, for example, for a file with name "thesisbiblio.bib":
    
    replace this line:
	\bibliography{./Bibliography}
    with this:
	\bibliography{./thesisbiblio}

=====================================================================================
5. Thesis Cover Logo/Picture
=====================================================================================
If you do not want a Thesis Logo (picture) in the cover 
just comment line 18 of 'Front_Cover.tex'

=====================================================================================
6. Page Numbering
=====================================================================================
If you want to have page numbers at the right/left (instead of Centered) 
of the page footer, then go to section "% Choose the positioning of the Page Number" 
at lines 248, 250, or 253 of the 'Preamble_commands.tex' and select your option.

=====================================================================================
7. Acronyms and Abbreviations
=====================================================================================
The template  includes a feature to simplify, and automate, the use of Acronyms 
and Abbreviations as well as print a List (Table) of the ones used in the document.
The general rule for using Acronyms, is to have them "defined" in the text on first use, 
and then just use the acronym in the remaining parts of the text.
The Acronyms package does precisely that, i.e., allows you to invoke the Acronym
with a command, e.g., \ac{CC},  and the tool just "knows" if is the first time or not,
so that either prints the extended meaning, e.g., "Cloud Computing (CC)" 
or just the Acronym "CC".

Acronyms are defined in the file  "Acronyms.tex" with the command \acro{ }{ }.

In the text you can invoke the Acronym definitions with the command \ac{ }, 
or \acp{ } for plural.
There are examples in the template files for you to see how this is done.

=====================================================================================
8. Glossary, Terms and Symbols
=====================================================================================
The template includes (optionally) a Glossary package that allow you to create a
List of Terms (a Glossary), as well as a List of Symbols used, that are Listed 
after the Bibliography.
Glossary and Symbol "Entries" are defined in the file  "Glossary.tex" with 
the command \newglossaryentry{ }.

In the text you can invoke the Glossary or Symbol entries with the command \gls{ }.
There are examples in the template files for you to see how it is done.

In case you do not use Symbology and/or Glossaries, then just comment 
in 'Preamble_commands.tex' the lines 366, 368 

and in ‘Main_Document.tex’ the lines with command "\printglossary[]{}", that appear 
after the invocation of the Bibliography, i.e., lines 226 and 233 in the current version.
=====================================================================================
9. Automatic naming of floats (Figures, Tables, etc.), 
   and document parts (Chapters, Sections, etc.)
=====================================================================================
The template includes a feature to simplify and automate the invocation of the 
correct "name" of floats, such as Figures, Tables, Algorithms, Listings, equations, 
as well as parts of the document, i.e., chapters, sections, etc.

For this to work you just need to add a \label{} with a unique name to those items.
For parts of the document (Chapters, Sections, etc.) the label is added 
after the command that starts each part.
For example:
- for a Section:
\section{Title the Section One}\label{sec:one}

- for a Figure, insert the label after the caption:
    \begin{figure}[h]
        \centering
        \includegraphics[width=0.9\textwidth]{./Images/cashed5}
        \caption{Ecosystem}
        \label{fig:cashed}
    \end{figure}

In the text you can then invoke the item with the command \Cref{fig:cashed}, 
in the case of the Figure or \Cref{sec:one} in the case of a Section, etc..
There are examples in the template files for you to see how it is done.

=====================================================================================
10. Other Features
=====================================================================================
The Template also includes examples of several other features, such as:
- "TODO NOTES", to help you take visible notes in the processed document for thigs to do.
- "TRACK CHANGES", to follow changes made, and by whom, in the case you share the document
   with you Supervisors
- use of "Table Generators" to allow creating quite complex tables and then just 
  paste the code in the document, 
- "Snippets of Code" with syntax highlighting, 
- Algorithms pseudo-code constructs. 
=====================================================================================
If you need some help or clarification you can contact me "rui.s.cruz@tecnico.ulisboa.pt"

Enjoy
Rui Santos Cruz