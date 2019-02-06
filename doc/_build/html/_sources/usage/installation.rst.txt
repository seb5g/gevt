=================
Installer GeVT
=================


.. contents::
   :depth: 1
   :local:
   :backlinks: none

.. highlight:: console

Overview
--------
GeVT est écrit en `Python`__ et supporte Python 3.5+. Il utilise la bibliothèque `PyQt5`__ pour son interface
utilisateur. Pour commencer, vous devez avoir une distribution de Python installée.

__ https://docs.python-guide.org/
__ http://doc.qt.io/qt-5/qt5-intro.html


La distribution Python recommandée est `WinPython`__ qui contient un ensemble conséquent de package pour une
utilisation versatile de python. Sous Linux et MacOS, une distribution similaire est accessible: `Anaconda`__.

Installation
------------

A partir des sources:
*********************

Depuis le repertoire local de GeVT (téléchargé depuis Github), il faut lancer la ligne de commande

::

  C:\...\GeVT\python setup.py install

Avec Pip:
*********

Il est cependant bien plus simple d'utilisaer l'utilitaire ``pip`` installé avec winpython. Pour cela:

* Télécharger winpython et l'installer (choisir un répertoire d'installation sur ``C:\`` directement,
  par exemple: ``C:\WPy-3710``
* ouvrir la ligne de commande depuis Winpython ``C:\WPy-3710\WinPython Command Prompt.exe``
* écrire la commande: ``C:\WPy-3710\scripts\pip install gevt``

__ https://winpython.github.io/
__ https://www.python.org/downloads/

