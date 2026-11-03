# Examens partagés et obligations par contexte

Suite de [J1 #123](https://github.com/Progideo/training_management/issues/123) et
du [moteur de passation](j1-shared-exam-runtime.md). Référence : cadrage consolidé
du 3 novembre 2026, D01/D02 et section 8.

## Offres et inscriptions TM

Les activités d’une offre TM peuvent référencer les versions publiées de la
bibliothèque `training_mock_exam` appartenant à la même formation et société.
Une offre peut sélectionner plusieurs examens ; plusieurs offres peuvent utiliser
une même version, sans copier les questions ou les réponses par offre.

Chaque affectation partagée choisit une obligation :

| Obligation | Complétion de l’activité | Effet sur l’achèvement |
| --- | --- | --- |
| Facultatif | Une tentative terminée | Ne bloque pas l’achèvement |
| Requis à passer | Une tentative terminée, même échouée ou clôturée à expiration | Bloque tant qu’aucune tentative n’est terminée |
| Requis à réussir | Une tentative atteint le seuil de la version affectée | Bloque tant que ce seuil n’est pas atteint |

Un lancement ne suffit pas. Le seuil, le barème et la durée appartiennent à la
version publiée. Le score est relu dans les réponses natives avec la dernière
révision motivée. Le meilleur résultat du contexte reste acquis après un échec
ultérieur. Aucun résultat d’un autre contexte ou d’une autre version n’est repris.

La confirmation d’inscription fige les références et obligations dans
`training.exam.requirement`. Il s’agit de liens pédagogiques immuables, sans
nouveau référentiel de participants ni seconde table de réponses. Une nouvelle
obligation ou version d’affectation nécessite une nouvelle offre ; les inscriptions
existantes ne sont pas réécrites. Les anciennes affectations par programme gardent
leur comportement historique et ne sont pas converties automatiquement.

La configuration et la confirmation utilisent le verrou natif de l’offre. Les
obligations figées empêchent la suppression ou la modification de l’affectation.
Le caractère facultatif reste cohérent avec les prérequis ; un examen facultatif
ne peut pas devenir un préalable caché d’une activité obligatoire.

## Droits et restitution

Le moteur commun calcule un état scalaire par personne, version et contexte.
Le contexte TM continue d’autoriser lancement, sauvegarde et lecture détaillée.
Le droit de lecture interne des réponses est fourni par l’adaptateur dans une
référence de groupe protégée, contrôlée avec la société ; il ne découle jamais
du rôle d’auteur des définitions. Les routes Survey et binaires génériques restent
fermées aux apprenants ; les images passent par la route privée du contexte.

Le profil qualité vérifie l’achèvement sans lire les questions. L’attestation
conserve son contrôle qualité et sa preuve dédiée ; aucun examen ne la délivre
seul. Les origines de l’attestation conservent la référence de l’obligation et le
seuil de la version lorsqu’une réussite est requise.

Pour les nouvelles affectations partagées, l’expiration ferme questions, réponses
détaillées, images et corrigés. Une sauvegarde arrivée après fin d’accès clôt la
tentative sans enregistrer de nouvelle réponse. Les états et scores restent
conservés. Le renouvellement du même contexte rétablit la consultation et garde
les obligations et historiques. Suspension et révocation restent plus restrictives.

## Limites et recette

Cette tranche raccorde les offres TM existantes. La règle d’obligation et le
contrat de lecture sont communs ; le socle `training_elearning` et son adaptateur
Survey restent à livrer. Le contexte TM historique de l’extension interactive
ne constitue pas une application autonome. Aucune migration métier historique,
reprise Odoo 19 ou bascule de production n’est qualifiée.

1. Créer deux offres utilisant la même version avec des obligations différentes ;
   confirmer les inscriptions et vérifier les références figées.
2. Refuser modification, suppression, autre formation/société et accès d’un tiers.
3. Vérifier lancement seul, remise à zéro, expiration, réussite puis échec et
   distinction de deux versions d’une famille. Une seule tentative de famille
   reste active par contexte ; terminer l’ancienne avant de changer de version.
4. Vérifier le portail, les images, la fin d’accès, le renouvellement et les
   attestations avec un profil qualité sans droit sur les questions.
5. Mettre à jour et comparer obligations, identifiants, réponses, délais et acquis.

Banc dédié : `python3 tests/ci/run_j2_obligations.py`. Les résultats d’exécution
restent dans les PR.
