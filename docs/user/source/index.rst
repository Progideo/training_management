Training Management
===================

Training Management gère le cycle d'une formation dans Odoo : catalogue,
demande commerciale, réalisation, inscriptions, apprentissage, présences,
évaluations, attestations et qualité. Ce manuel explique les actions quotidiennes
et les décisions à prendre pour chaque profil.

Commencer par :doc:`demarrage`, puis consulter le chapitre correspondant à son
rôle. Les procédures utilisent les libellés français de l'application. Les menus
visibles dépendent des modules installés, des droits et des sociétés sélectionnées.

.. important::
   Édition du 1 novembre 2026 pour Training Management sur Odoo Community 20.
   Les écrans disponibles dépendent des modules installés et de vos habilitations.
   La version exacte et le périmètre documenté figurent dans :doc:`references`.

Les captures sont nouvelles et proviennent d'une base isolée contenant des données
fictives. Elles illustrent un écran et un contexte précis ; leurs dates,
libellés de test et paramètres ne sont pas des valeurs à reproduire.
Voir :doc:`references` pour leur provenance et les limites de couverture.

Choisir son parcours
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Vous êtes…
     - Commencer ici
   * - Administrateur
     - :doc:`administration` : modules, comptes, sociétés, droits et notifications.
   * - Coordinateur
     - :doc:`catalogue`, :doc:`organisation`, puis :doc:`pedagogie`.
   * - Commercial ou facturation
     - :doc:`commercial` : demandes, contrats et documents natifs Odoo.
   * - Participant
     - :doc:`participant`, :doc:`examens`, :doc:`apres-formation`.
   * - Formateur, tuteur ou évaluateur
     - :doc:`formateur`, :doc:`presences`, :doc:`evaluations`.
   * - Représentant d'entreprise cliente
     - :doc:`entreprise` : lots autorisés, nominations, programme intra et documents.
   * - Responsable qualité
     - :doc:`qualite`, :doc:`attestations`, :doc:`evaluations`.
   * - Superviseur
     - :doc:`pilotage` : indicateurs et périmètres de lecture.
   * - Modérateur
     - :doc:`apres-formation` : avis vérifiés et cas clients.
   * - Visiteur
     - :doc:`catalogue-public` : choisir, demander conseil et suivre les dates publiques.

.. toctree::
   :maxdepth: 1
   :caption: Découvrir et administrer

   demarrage
   administration

.. toctree::
   :maxdepth: 1
   :caption: Organiser et commercialiser

   catalogue
   catalogue-public
   commercial
   organisation
   entreprise

.. toctree::
   :maxdepth: 1
   :caption: Apprendre et accompagner

   participant
   pedagogie
   examens
   formateur
   presences
   evaluations
   apres-formation

.. toctree::
   :maxdepth: 1
   :caption: Contrôler et clôturer

   attestations
   qualite
   pilotage
   assistance
   references
