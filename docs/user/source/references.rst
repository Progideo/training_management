Références et périmètre du manuel
=================================

Version documentée
------------------

Ce manuel décrit le dépôt ``Progideo/training_management`` au commit
``27e9e96b8164a69d9adaaba3982c34572cd97f0f``. Le chapitre des présences est
actualisé pour la version ``20.0.2.11.0``, livrée par la PR #112 au commit
``8393622d9e8978f7f1baabf4efff10d4b56bb7f9`` le 1 novembre 2026. Les règles sont relues dans la
spécification amendée, les décisions durables, les modèles, vues et traductions
du dépôt. Les spécifications historiques ne sont pas traitées comme une liste
de boutons disponibles.

La cible vérifiée du projet est Community ``20.0-20261015``. Le manuel couvre
le socle, P01 à P14, P16 et P20 ; P15 est annulé, P17 à P19 restent reportés.
Les restrictions historiques MAD/EUR et virement ne sont pas les règles du
module générique depuis la décision #102.

La présentation reprend les conventions de la
`documentation utilisateur Odoo <https://www.odoo.com/documentation/19.0/fr/applications.html>`_ :
chapitres thématiques, navigation, chemins de menus, procédures, figures et
encadrés. Le manuel est propre à Training Management. La documentation Odoo 19
sert de référence éditoriale, pas de preuve de compatibilité Odoo 20.

.. note::
   Les procédures reflètent le code et les références métier identifiés.
   Les captures montrent les parcours effectivement ouverts dans la base
   de démonstration. Elles ne constituent pas une nouvelle recette exhaustive
   de toutes les permissions et intégrations. Les résultats techniques du
   projet restent dans les pull requests et la CI.

Sources métier par chapitre
---------------------------

Les documents cités se trouvent dans le répertoire ``docs/`` du dépôt, à la
révision de référence ci-dessus. L'index du dépôt et les liens de code permettent
de retrouver le détail des règles sans dupliquer les documents techniques.

.. list-table:: Traçabilité
   :header-rows: 1

   * - Chapitres
     - Sources du dépôt
   * - Administration et démarrage
     - ``AGENTS.md``, ``README.md``, ``native-coverage.md``, ``s11-security-audit.md`` ; manifests et ``security/`` des addons.
   * - Catalogue et catalogue public
     - ``catalogue-categories-pdf.md``, ``p01-p02-guided-requests.md``, ``p03-p04-public-catalogue.md``, ``p10-orientation.md``, ``p16-session-status-alerts.md``.
   * - Commercial
     - ``native-commercial-accounting.md`` (#102), ``native-rules-followup.md``, ``s02-1-document-policy.md``, ``p09-commercial-paths.md``.
   * - Organisation et entreprise
     - ``s03-enrollment-access.md``, ``s03-1-review-fixes.md``, ``s04-preparation-sessions.md``, ``p05-p06-company-dossiers.md``.
   * - Participant et pédagogie
     - ``s05-private-materials.md``, ``p09-learning-paths.md``, ``p09-participant-portal.md``, ``p12-assessed-projects.md``, ``p13-tutoring-booking.md``.
   * - Examens blancs
     - ``s06-mock-exams.md`` ; modèles, contrôleurs et vues de ``training_management_survey``.
   * - Formateur et présences
     - ``s04-preparation-sessions.md``, ``s07-attendance.md``, ``s07-attendance-signatures.md`` (#111/#112), ``review-experience-performance.md``, ``review-access-continuity.md``.
   * - Évaluations et retours
     - ``s091-evaluations.md``, ``s092-feedback.md`` ; services d'évaluation et de campagnes.
   * - Après formation et publications
     - ``p11-practice-plans.md``, ``p14-verified-reviews.md`` ; services et gabarits de mise en pratique et publications.
   * - Attestations
     - ``s08-closure-documents.md``, ``p20-verifiable-certificates.md``, ``review-access-continuity.md`` ; rapports QWeb.
   * - Qualité et pilotage
     - ``s093-quality.md``, ``s094-intervenants-veille.md``, ``s10-operational-dashboard.md``, ``s11-security-audit.md``.

`Consulter les références au commit documenté <https://github.com/Progideo/training_management/tree/27e9e96b8164a69d9adaaba3982c34572cd97f0f/docs>`_.

Captures et données de démonstration
------------------------------------

Les captures du manuel sont produites à nouveau le **1 novembre 2026** sur
une base locale isolée, avec le code de référence indiqué dans ``screenshots.json``. Les deux
captures de signatures utilisent le code de la PR #112, identique pour les
addons au commit de livraison ci-dessus ; leurs libellés sont en anglais et
leurs comptes et dessins sont fictifs. Les tâches planifiées
et serveurs de courrier sortant sont désactivés pour cette base. Elle n'utilise
ni export client, ni sauvegarde de production, ni coordonnées réelles.

L'organisme **Atelier Horizon — démonstration**, l'entreprise **Société Démo
Atlas**, les personnes, leurs travaux et décisions sont des données synthétiques.
Le scénario illustre le pilotage d'un projet et son accompagnement. Les adresses
utilisent des domaines d'exemple non destinés aux envois.

Les fichiers originaux sont dans ``source/images/`` et copiés dans les ressources
du HTML par la génération. Le manifeste ``screenshots.json`` conserve pour
chaque image sa date, son rôle, son écran et son empreinte SHA-256.
Les dates et quantités visibles illustrent uniquement la démonstration : elles
ne fixent aucune durée de conservation, tarif ou politique obligatoire.

Limites et mise à jour
----------------------

Les menus peuvent différer selon langue, modules, droits et société. Le rôle
administrateur n'est pas le profil normal utilisé pour les captures pédagogiques.
Des fonctions optionnelles n'apparaissent que si l'intégration correspondante
est installée. Les prestataires, localisations et extensions tiers demandent
leur propre validation.

Lors d'une évolution, vérifier les règles dans le nouveau code, mettre à jour
le chapitre concerné, refaire les captures affectées et régénérer le HTML.
Le fichier ``docs/user/README.md`` décrit la génération et la vérification.
Les sources synchronisées du projet ChatGPT restent en lecture seule.
