# S10 — Tableau de suivi, indicateurs et notifications

Réf. [issue #20](https://github.com/Progideo/training_management/issues/20),
NOT01, PIL01, UX01 et [contrat S09](s09-evaluations-quality.md#contrat-des-états-consommés-par-s10).

## Règles

**Formations → Tableau de suivi** présente une ligne par inscription, sans jointure
multiplicative. Tous les états sont retrouvables, y compris annulations et abandons.
La fiche et la synthèse par réalisation réutilisent les sources S07–S09 ; un lien
portail donne la même consultation aux formateurs externes affectés. Un superviseur
consulte sa réalisation sans recevoir de pouvoir de validation. Le formateur voit
ses séances ; le coordonnateur et les référents explicitement affectés conservent
leurs périmètres. Listes, regroupements, filtres, détails et exports revérifient les
droits et les sociétés sélectionnées. Aucun nouveau droit comptable ou qualité
confidentiel, aucun devoir, remise ou échange privé n’est publié dans le tableau.

La date de situation est l’extraction actuelle. La période filtre les débuts de
séance et les échéances des évaluations/questionnaires ; elle ne reconstitue pas
un ancien tableau. La population après filtres est affichée. Les campagnes gardent
leur population d’origine : les filtres nominatifs ne recalculent pas leurs agrégats.
Les retours formateur/commanditaire restent au niveau de la réalisation.

La présence attendue vient du planning et de l’état confirmé au début de séance,
retrouvé dans l’historique S03. Une déclaration, un dépôt papier et une validation
restent distincts. La dernière validation/correction fait autorité. Sans séance,
l’asynchrone est non applicable ; un planning daté manquant reste une donnée manquante
et apparaît dans le filtre des émargements à contrôler.
Les justificatifs et leurs corrections ne sont liés que si leur lecture est autorisée.

Une évaluation sans résultat ne vaut pas zéro. Les acquis sont groupés par définition
et version : validations au seuil / évaluations notées validées, avec couverture
validées / affectées applicables. Les reprises ne multiplient pas les participants.
Les examens blancs gardent premier, dernier et meilleur score et nombre de tentatives
par version, séparément du taux d’acquis. Aucune certification officielle n’en découle.
La présence mesure minutes validées / minutes planifiées applicables ; sa couverture
compte des couples inscription/séance. Zéro dénominateur signifie « non calculable ».

Le remplissage distingue places confirmées et réservations. L’abandon porte sur les
inscriptions confirmées au démarrage. La complétion globale réutilise les critères
requis S05, sans en afficher les contenus privés, pour les parcours arrivés à échéance.
Les critères ou échéances manquants restent visibles. Les indicateurs sont versionnés
`S10-1` ; les exports natifs portent sur les colonnes du tableau, sans traversée
des référentiels sources, et conservent un manifeste du périmètre autorisé.

L’anonymat conserve strictement S09.2 : aucune réponse/non-réponse nominative ;
restitution du seul agrégat figé après clôture dès **3 réponses recevables**, sans
contrôle supplémentaire. Deux réponses ne livrent ni taux ni petit comptage.

Les intégrations optionnelles fournissent les montants par devise, sans addition
MAD/EUR : ventes des lignes affectées ; cohorte entière des factures liées aux
commandes affectées, moins avoirs ; paiements clients natifs de la société sur la
période, explicitement non ventilés par réalisation. Les références rapprochées
restent distinctes. La conversion porte sur les opportunités actives du programme
créées dans la période ; les demandes non qualifiées et archives/fusions sont exclues.
Ces périmètres et les références sources restent vérifiables par les habilités.
La marge reste différée tant que les coûts directs et taux nécessaires manquent.

## Notifications et accessibilité

Le tableau consolide les journaux S04, les relances S05 hors échanges privés et S09.2.
Les nouveaux avis couvrent demande/confirmation d’inscription, invitation/échéance
d’évaluation, attestation disponible et accusé de demande CRM. Ils utilisent la file
native `mail.mail`, un destinataire par message, un journal durable et une clé unique.
Un rejeu réutilise l’envoi ; une erreur reste visible. Le transport revérifie le
bénéficiaire actuel, le contenu générique et l’absence de copie/pièce jointe.
Les anciens modèles ne reçoivent pas de version historique inventée : leur courriel
conservé fait référence. Aucune notification rétroactive n’est créée à la mise à jour.

La consultation utilise listes/formulaires natifs, QWeb et Bootstrap, avec libellés,
états textuels et filtres accessibles au clavier. Une période incohérente conserve
les filtres et affiche une erreur explicite, sans calculer de faux totaux. **Contrôles d’accessibilité PDF**
permet au référent qualité déjà habilité à la source de consigner ses vérifications
humaines : ordre de lecture, alternatives, contraste, texte/navigation et pédagogie.
Le contrôle conserve l’empreinte du fichier, l’auteur, la date et les écarts ; une
correction appelle une nouvelle revue. Il ne certifie pas l’accessibilité du PDF.

## Recette courte

1. Avec des données fictives, préparer quatre inscriptions dont une annulée,
   deux séances électronique/papier et un formateur/superviseur affectés. Ouvrir
   le tableau : une ligne par inscription ; filtres réalisation/état/séance/période
   et éléments à terminer concordants avec les sources.
2. Déclarer une demi-journée présente, déposer un papier, valider une absence puis
   corriger une présence. Vérifier états, minutes, historique et liens autorisés.
   Contrôler aussi un asynchrone sans séance et une annulation avant démarrage.
3. Affecter des évaluations non commencées, soumises et validées, dont un score nul.
   Vérifier 10 réussites sur 12 validations parmi 20 affectations : 83,33 %, couverture
   12/20. Vérifier « non calculable » sans validation et les examens blancs séparés.
4. Clore une campagne anonyme avec deux puis trois réponses identiques : seule la
   seconde restitue l’agrégat, sans contrôle supplémentaire ni état individuel.
   Vérifier les retours formateur/commanditaire dans la synthèse de réalisation.
5. Tester un autre client/réalisation, une autre société, un lecteur sans mission,
   puis retirer l’affectation : listes, ancien lien, total, détail et export refusés.
6. Rejouer une notification, simuler un échec et retirer le bénéficiaire : un seul
   journal/envoi, erreur visible, envoi devenu interdit. Vérifier les devises séparées,
   les acomptes/factures/avoirs et les périmètres commerciaux affichés.
7. En français, à 390 puis 320 px et au clavier, appliquer les filtres, lire les états,
   ouvrir un détail et revenir. Vérifier focus, défilement et erreurs textuelles.
8. Consigner un contrôle humain de PDF avec écarts ; vérifier empreinte et immutabilité.
   Contrôler séparément le PDF avec les outils et lecteurs adaptés au public visé.

Les [règles de lecture par lots et de pagination](review-experience-performance.md)
conservent les agrégats globaux et limitent les détails à la page visible.
