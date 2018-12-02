=====
About
=====


.. contents::
   :depth: 1
   :local:
   :backlinks: none

.. highlight:: console


GeVT est une interface utilisateur (voir :numref:`figure_example`) qui permet la gestion semi-automatisée d'événements nécessitant des bénévoles. Plus le nombre de tâches à effectuer et à répartir parmis de nombreux bénévoles est grand plus la gestion de l'affectation de ces tâches devient complexe. GeVT permet de:

* **Edition de la liste des tâches** à effectuer durant les différents jours de l'événement. Importation depuis un fichier au format *csv* possible, voir :ref:`template-csv-tasks`.
* **Edition de la liste des volontaires** (bénévoles) et de leur disponibilité. Importation depuis un fichier au format *csv* possible, :ref:`template-csv-vol`.
* **Affectation d'un ou plusieurs bénévoles** (selon le nombre nécessaire *N needed*) à une tâche donnée selon leur disponibilité. Si un bénévole n'est pas disponible sur le créneau de la tâche, il n'apparait pas dans la liste des possibilités.
* **Affectation d'une ou plusieurs tâches** à un bénévole. La liste des tâches *affectables* est mise à jour immédiatement selon les tâches précédemment sélectionnées et qui modifient la disponibilité du bénévole.
* **Timeline** pour voir l'état des différentes affectations
* Edition automatique de fiches bénévoles regroupant l'ensemble des tâches qu'un bénvole devra effectuer.


   .. _figure_example:

.. figure:: ../images/example.png
   :scale: 80 %
   :height: 500px
   :alt: Starting message
   :align: center

   Example de l'interface de GeVT utilisé ici pour le Raid Tout Absolu (http://absoluraid.wixsite.com/absoluraid).