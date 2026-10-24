# S09.2 — Retours et campagnes

Références : [#19](https://github.com/Progideo/training_management/issues/19),
[EVA02 et cadrage S09](s09-evaluations-quality.md). S10 reste la vue consolidée.

## Parcours

1. Dans Formations → Versions des retours, choisir programme, finalité immédiate,
   différée, formateur ou commanditaire, version, critères et mode nominatif/anonyme.
   Créer le questionnaire dans l’éditeur Survey natif. Choix fixes et texte sont
   acceptés ; coordonnées, pseudonyme et questions conditionnelles sont exclus.
   Pour un taux de satisfaction, désigner une question QCU et les choix favorables.
   Publier fige le contenu ; « Nouvelle version » conserve l’original.
2. Créer une campagne sur une réalisation : population motivée, ouverture,
   échéance, politique de conservation S08 approuvée et intervalle de relance
   (zéro désactive les relances automatiques).
   Affecter explicitement les destinataires et leur rôle. Les participants doivent
   avoir une inscription confirmée non suspendue/révoquée ; l’expiration normale
   des supports ne bloque pas un retour différé. Une mission formateur courante
   est exigée ; le commanditaire reçoit une invitation explicitement autorisée.
3. Ouvrir puis inviter. Le planificateur natif met aussi les invitations en file
   à partir de l’ouverture et déclenche les relances configurées. Le journal
   conserve destinataire, occurrence et résultat de file. Répéter une occurrence
   ne multiplie pas les envois ; une erreur de transport peut être reprise.
4. Répondre depuis « Mes retours de formation », avec le compte Odoo invité.
   Le nominatif peut enregistrer un brouillon et le reprendre. Le mode anonyme
   remet tout le formulaire ensemble, sans brouillon identifié ni statut individuel.
5. Clôturer fige la synthèse. La nouvelle collecte conserve l’ancienne échéance
   et son bilan, puis propose une campagne distincte à paramétrer. Aucun ancien
   résultat n’est réécrit.
6. « Créer la preuve S08 » dépose uniquement le PDF de campagne/synthèse dans un
   dossier ouvert de la même réalisation. Catégorie `feedback`, validation qualité
   et conservation S08 habituelles ; exclusion des exports client inchangée.

## Anonymat et droits

La restitution collective est disponible **après clôture dès trois réponses
recevables**, sans autre contrôle, y compris pour trois réponses identiques.
En dessous, seul « effectif insuffisant » est conservé dans la restitution.
Une réponse recevable est une remise complète selon les obligations de la version,
avec au moins une réponse. Les brouillons et non-réponses ne sont jamais favorables.

Les invitations administratives ne sont pas modifiées par une remise anonyme.
Les réponses Survey ne portent ni inscription, invitation, contact, courriel,
pseudonyme ni auteur personnel. Leurs dates techniques sont neutralisées sur la
date d’ouverture ; les débuts/fins individuels ne sont pas conservés. L’ORM force
ces dates : deux mises à jour SQL paramétrées, limitées aux nouvelles réponses
anonymes et à leurs lignes dans la même transaction, retirent ce rapprochement.
Aucun message, fichier, courriel ou journal applicatif de réponse n’est créé.

Un registre technique séparé, sans droits métier ni dates techniques, conserve
un ensemble trié d’empreintes anti-double-remise par campagne. Sa clé est figée
dans ce registre privé pour préserver l’unicité après rotation du secret Odoo.
La mise à jour reprend la clé courante des registres existants. Aucune relation
avec les réponses ou ordre individuel de remise n’y figure. Le formulaire utilise
l’authentification Odoo et revérifie l’invitation et l’éligibilité à chaque remise ;
aucun lien public transférable n’est délivré. Un verrou de réalisation sérialise
remises, retraits et clôture. Les privilèges techniques de base/support restent
hors des droits métier, comme dans SEC01 ; ceci ne prétend pas protéger contre
l’administrateur de la base ou une journalisation externe des corps HTTP.

Les relances anonymes concernent tous les invités encore éligibles, répondants
compris. Ni coordination, qualité, formateur, superviseur ni destinataire ne
reçoivent de statut nominatif anonyme. Les lectures/recherches/regroupements/
exports natifs des réponses Survey sont bloqués pour les rôles métier, ainsi que
les anciens liens Survey. Les sondages ordinaires et S06/S09.1 gardent leurs règles.
Le texte libre avertit contre l’auto-identification ; aucun verbatim anonyme n’est
restitué individuellement. Les synthèses présentent les distributions des choix
et la couverture des questions textuelles, sans publier ces textes.

La coordination gère les campagnes de ses sociétés. Le superviseur et la qualité
lisent les synthèses de leurs seules réalisations affectées ; le formateur utilise
la projection portail pour sa mission courante. Les réponses nominatives complètes
sont projetées uniquement à la coordination ou à la qualité affectée. Un client
ne reçoit pas automatiquement une synthèse ni les résultats de ses salariés.
Retirer l’affectation retire aussi l’accès aux anciens liens. Les envois contrôlent
encore l’éligibilité, l’adresse et l’enveloppe au transport, y compris en reprise.

Les états nominatifs distinguent non invité, en file, erreur d’invitation, invité,
en cours, réponse reçue et non-réponse à échéance ; seule une invitation envoyée
peut produire une non-réponse administrative. Le non-applicable/retrait est motivé.
Les états anonymes restent indisponibles, indépendamment des relances.
Une relance nominative en attente est refusée au transport si la réponse est
entre-temps reçue. L’ouverture revérifie la population après modification du
brouillon ; les destinataires ne peuvent pas consulter une campagne en brouillon.
Les textes libres sont conservés intégralement selon les limites natives du
questionnaire, sans troncature silencieuse.

La synthèse `S092-1` conserve version, population, période, reçus/attendus/applicables,
valides et favorables par question indicatrice. Taux = favorables / valides ;
dénominateur nul = non calculable. Une réponse négative compte comme valide.
Aucune déduction individuelle, aucun indicateur de certification.
Les politiques et responsables de conservation doivent être approuvés avant
collecte réelle ; aucun délai juridique ni purge automatique n’est ajouté.
Socle `20.0.1.10.0`, intégration Survey `20.0.1.2.1` ; le socle reste installable seul.

## Recette courte

- Deux réalisations/sociétés, trois comptes fictifs : publier V1, planifier une
  ouverture différée puis inviter. Rejouer invitation et relance ; vérifier file,
  erreurs et reprise. Retirer un destinataire avant le transport : envoi refusé.
- En anonyme, remettre deux réponses puis clôturer : effectif insuffisant. Dans
  une autre campagne, remettre trois réponses identiques et clôturer : synthèse
  disponible, sans condition supplémentaire. Double clic : une seule réponse.
- Vérifier que tous les invités éligibles reçoivent la relance collective, sans
  statut de début/réponse/non-réponse individuel. Contrôler ORM, export, rapports,
  métadonnées et anciens liens. Ne publier aucun texte libre individuel anonyme.
- En nominatif, enregistrer, reprendre, remettre ; distinguer brouillon, réponse
  reçue, non-réponse et non-applicable. Tester une seule invitation formateur ou
  commanditaire sans fabriquer des inscriptions participant.
- Modifier la réalisation ou le public d’un brouillon déjà peuplé : ouverture
  refusée tant que les invitations ne conviennent plus. Son URL reste inaccessible
  aux destinataires. Vérifier un texte de plus de 20 000 caractères, une rotation
  du secret après remise anonyme et une réponse après mise en file d’une relance
  nominative : texte intact, aucune double remise et aucune relance devenue inutile.
- Superviseur affecté puis retiré, qualité affectée/non affectée, autre client et
  société étrangère : vérifier listes, liens, synthèses et preuves. Contrôler au
  clavier et en largeur 320/390 px : labels, conservation de saisie après erreur,
  focus sur le message et absence de débordement. Inclure une réponse nominative
  sur plusieurs lignes avec une URL longue ; vérifier les noms dans le journal
  des invitations et relances.
- Clôturer, créer le vrai PDF S08 puis une nouvelle collecte/version ; comparer
  les anciens PDF et synthèses. Vérifier l’exclusion client et le gel du dossier.
- Exécuter [run_s092.sh](../tests/ci/run_s092.sh) : mise à jour depuis S09.1 avec
  Website, historiques S02–S09.1, installation vierge, socle seul, seconde mise à
  jour et transactions concurrentes. Résultats et limites dans la PR.
