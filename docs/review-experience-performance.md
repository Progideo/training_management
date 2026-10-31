# Reprise d’examen, portail, demi-journées et suivi

Références : EXA03, P07, UX01, PRE01–03 et PIL01 de la
[spécification](references/Training_Management_Specification_Fonctionnelle_v2.md).

## Parcours

- **Examen** : après un échec réseau, les dernières réponses et marquages restent
  dans la page ouverte. « Réessayer » contrôle l’état serveur puis sauvegarde les
  changements encore autorisés. Chaque question distingue réponse reçue et
  changement non confirmé. La remise attend les accusés de réception. Après
  échéance, aucun changement local n’est rejoué ; recharger ferme les modifications
  non reçues. Aucun stockage persistant des réponses dans le navigateur.
- **Portail** : l’accueil conduit à « Mes formations ». Cet espace réunit formations
  actives, actions et historiques autorisés, puis responsabilités réellement
  affectées. Les cumuls de missions sont conservés ; chaque destination continue
  de vérifier ses droits côté serveur.
- **Émargement** : choisir présent ou absent, puis confirmer la demi-journée.
  Le matin précède midi et l’après-midi commence à midi, dans le fuseau du planning.
  Chaque séance est découpée à ces limites ; les pauses doivent figurer dans le
  planning entre les séances. Une confirmation couvre les séances électroniques
  de cette demi-journée, chaque formateur validant celles qui lui sont affectées.
  La durée retenue est la durée prévue des parties présentes et validées, sans
  forfait. Papier, correction motivée, contrôle distinct, refus des droits retirés
  et horodatage serveur sont conservés.
- **Anciennes présences** : leurs intervalles, auteurs, fichiers et durées restent
  inchangés. Avant de les remplacer par des demi-journées, les invalider avec motif.
  Les preuves restent consultables ; leur durée invalidée ne s’ajoute pas aux nouvelles.
- **Tableau de suivi** : les présences, transitions, évaluations et états nominatifs
  des questionnaires sont lus par lots. Les totaux couvrent toute la population
  filtrée. Historiques détaillés et tentatives ne sont chargés que pour la page
  visible. Les réponses anonymes ne sont pas lues pour établir un état individuel.

## Recette courte

1. Pendant un examen, couper le réseau, changer une réponse et un marquage,
   reconnecter puis réessayer. Vérifier les accusés, la remise et le refus de
   changements après l’échéance serveur ; garder aussi une tentative ancienne.
2. Comparer l’accueil participant, formateur, tuteur, entreprise et cumul de rôles.
   Retirer une mission et vérifier sa disparition ainsi que le refus du lien direct.
3. Sur mobile, confirmer une matinée et déclarer une après-midi absente, sans
   saisir d’heures. Faire valider par un autre utilisateur, vérifier la durée de
   l’attestation, un papier signé, une correction et une double soumission.
4. Vérifier un planning dans un autre fuseau, une séance traversant midi et
   plusieurs séances le même matin. Une période non écoulée reste refusée.
5. Avec plusieurs séances et 100 participants, changer page et filtres : les
   détails changent, les agrégats restent ceux de toute la population filtrée.

Les résultats d’exécution et limites de validation restent dans la livraison.
