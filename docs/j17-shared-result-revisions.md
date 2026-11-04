# J17 — Révisions motivées et qualification des contextes

Le moteur commun `training_mock_exam` porte les révisions de résultats.
Les noms des modèles et tables TM restent identiques : anciennes réponses,
notes initiales, délais, motifs et chaînes de révisions sont conservés.

Chaque adaptateur autorise sa propre coordination, sa société et son contexte.
Un auteur de banque ne devient pas correcteur des résultats. Une habilitation TM
ne donne aucun accès aux résultats autonomes, y compris aux formulaires temporaires.
Les révisions sont immuables ; les fichiers et pièces jointes génériques sont refusés.

Le formulaire affiche les points précédents et impose un motif. Tous les points
sont contrôlés contre les maxima des questions figées. Un identifiant de requête
rend la validation répétable ; un formulaire préparé avant une autre correction
est refusé. Une écriture de sérialisation protège aussi les transactions dont la
lecture est devenue ancienne. L’événement et la projection pédagogique sont atomiques.
Les réponses, le score initial et le chronomètre ne sont jamais réécrits.

Dans le contexte autonome, une révision de note ne retire pas implicitement un acquis. La synthèse privée
active présente le résultat révisé et les motifs ; les dates utilisent le fuseau
du titulaire. Les adaptateurs gardent leurs propres règles de progression.

La qualification de coexistence couvre aussi les routes HTTP des deux lecteurs.
Leurs méthodes de contrôleur portent des noms distincts : l’assemblage natif Odoo
des extensions du même contrôleur ne doit pas masquer les routes d’un autre mode.
Le déplacement technique neutralise l’installation automatique des addons retirés,
y compris leurs métadonnées découvertes avant installation ; voir [J15](j15-module-layout.md).

## Recette courte

1. Terminer un examen, ouvrir le formulaire natif et corriger avec motif.
   Vérifier score initial, réponses et temps inchangés, nouvelle note et historique.
2. Répéter la validation, puis utiliser un ancien formulaire : même événement au
   premier rejeu, refus du formulaire périmé.
3. Retirer le rôle autonome à un compte gardant son rôle TM : les résultats et
   formulaires autonomes deviennent inaccessibles. Rejouer le refus entre sociétés.
4. En transactions distinctes, provoquer un verrou puis une lecture ancienne ;
   reprendre après annulation sans événement supplémentaire.
5. Mettre à jour depuis la génération précédente et comparer les traces natives.
   Installer séparément et en coexistence, puis ouvrir les deux lecteurs privés.

Suivi : [eLearning #19](https://github.com/Progideo/training_management_elearning/issues/19).
Les résultats exécutés et les limites restent dans les PR.
