# P12 — Projet pratique évalué

Référence : [#35](https://github.com/Progideo/training_management/issues/35),
chapitre 21 / P12, PED01, PED02 et DOC02 de la spécification v2.

## Couverture et décisions

Dans Community `20.0-20261015` (image `61e3c71b0503`), `mail.activity`
porte une échéance et un utilisateur interne ; `action_feedback` / `_action_done`
ne portent pas le contrat de grille et de remises versionnées. La progression
`slide.channel.partner._recompute_completion` est liée à l’adhésion eLearning,
sans rattachement à l’inscription S03. `project.task` propose affectations,
étapes, pièces jointes et notation de satisfaction ; son portail utilise
`_document_check_access`. Il faudrait lui ajouter les droits S03/S09, les remises
immuables et la grille, avec les dépendances Project/Analytic/Rating. Les remises privées S05 et les habilitations
S09 représentent déjà ces liens : extension ciblée du socle, sans dépendance,
service ni interface séparés. P11 et les évaluations S09 restent distincts.

Une **activité S05 avec grille** devient explicitement un projet. Elle porte
livrable attendu, référence de prestation, réalisation/formation, politique S08
approuvée et critère « Validation du tuteur ». Sans grille, le circuit S05 reste
inchangé. L’inscription existante porte le participant et ses versions de remise.
Le projet contribue à la progression S05 selon son caractère obligatoire/facultatif
et ses préalables ; aucune seconde progression ni score d’examen n’est créé.

## Parcours et habilitations

La coordination crée une grille depuis **Formations → Grilles de projets pratiques**.
Chaque critère décrit quatre niveaux : non acquis, en cours d’acquisition, acquis,
maîtrisé. Publier fige critères et descriptions. **Nouvelle version** copie la grille
en brouillon avec référence à l’original. Un projet ayant du travail est conservé ;
une nouvelle grille s’affecte à une nouvelle activité, sans réévaluer le passé.

L’évaluateur est le tuteur S05 affecté, individuellement ou sur la réalisation.
Le responsable qualité S09 lui attribue une habilitation **Projet pratique** par
réalisation et période ; une mission pédagogique courante est aussi requise.
Aucun rôle de coordination, qualité, supervision ou formateur ne suffit seul.
Le participant ne peut jamais évaluer son propre projet, même en cumul de rôles.

Dans **Mes formations**, le participant consulte livrable et grille puis dépose
texte et/ou fichier (20 Mo maximum). Dans **Mes accompagnements**, l’évaluateur
consulte la dernière remise et son fichier, puis l’évalue dans le formulaire placé
juste sous cette réponse. Il choisit un niveau par critère, saisit un retour
motivé, puis demande une révision ou accepte. La décision reste humaine : aucun seuil numérique implicite.
Une nouvelle remise référence la précédente ; une décision vise la dernière
remise. Corriger une décision exige un nouveau retour motivé et conserve les
précédents. Une nouvelle remise ou demande de révision retire la complétion
courante ; l’acceptation la rétablit. Une ancienne page doit être rechargée.

Chaque remise et décision conserve la grille exacte (identifiant de version,
libellés et descriptions), la définition du livrable, la prestation et la politique.
Les décisions conservent aussi les niveaux retenus ; auteur, date serveur,
message natif et original joint restent immuables. Une empreinte relie la décision
à l’origine de clôture S08, sans copier les retours privés dans l’attestation.
Le projet ne remplace pas la preuve d’acquis notés exigée pour une réussite S08.

## Confidentialité et conservation

Droits S05 courants pour le participant ; mission, affectation et habilitation
P12 courantes pour l’évaluateur. Le retrait de l’un de ces droits bloque travaux,
messages, résultats et fichiers, y compris liens natifs et anciens jetons.
La coordination conserve les paramètres et états de progression S05 ; son rôle
seul ne donne aucun accès aux travaux ou évaluations détaillées. Aucun accès
implicite du commanditaire, employeur ou superviseur ; aucune synthèse P11
alimentée automatiquement. Les profils portail n’obtiennent pas de droits ORM.

Les verrous réalisation/inscription et clés de requête S05 sérialisent remises et
décisions. Les modifications de critères et la publication sérialisent aussi
la grille : une page périmée ne peut publier une grille devenue vide. Une répétition conserve une preuve et une notification. Le journal
et la file native S10 restent génériques, sans résultat, consigne ni fichier.
Le transport revérifie aussi l’habilitation P12 actuelle du destinataire évaluateur.
Les échéances/rappels S05 configurés restent applicables ; aucune relance P11
ni envoi rétrospectif n’est créé à la mise à jour.

La politique S08 doit couvrir livrables, grilles, retours et décisions avant collecte
réelle. Pas de délai juridique inventé ni purge automatique. Les originaux et
historiques restent conservés et non exportables en masse selon S05/S11.
Les accès pédagogiques gardent le cycle S05, y compris sa clôture ; P12 ne crée
pas l’accès après formation particulier de P11. Les mises à jour ne créent aucun
projet, habilitation ou donnée pédagogique sur les inscriptions existantes.

## Recette courte

1. Sur base fictive, créer une grille depuis un formulaire vide, publier, définir
   un projet avec conservation approuvée, puis affecter tuteur, mission et habilitation.
2. Participant : remettre, évaluer chaque critère avec demande de révision,
   déposer V2 puis accepter. Vérifier progression unique, auteurs, dates et fichiers.
3. Corriger une décision avec motif et publier une grille V2 : historique V1 identique.
   Refuser champs incomplets, page périmée et validation par le participant.
4. Tester pair, client, autre société, coordination et évaluateur sans habilitation,
   puis retirer mission, habilitation ou affectation et reprendre anciens liens/jetons.
5. Répéter et concurrencer remise/validation : une preuve et notification par action.
   Vérifier le refus de transport après révocation et la conservation des remises simples.
6. En français, à 320/390 px et au clavier : consulter grille, saisir, corriger une
   erreur avec retour et niveaux conservés, télécharger l’original. Installer puis
   mettre à jour deux fois ; comparer grilles, décisions, fichiers et historiques S05/P11.
