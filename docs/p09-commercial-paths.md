# P09.3 Commercialisation des parcours

Référence : [P09 #32](https://github.com/Progideo/training_management/issues/32),
spécification §21 ; [composition](p09-learning-paths.md) et
[portail](p09-participant-portal.md). Cadrage validé le 28 octobre 2026 ;
les prix convenus au devis prolongent la décision commerciale [#10](https://github.com/Progideo/training_management/issues/10).

## Offre et prix

Une personne ou un groupe peut acheter le parcours complet ou une sélection de
ses formations. « Module » désigne ici une formation du parcours, pas une leçon.
Le devis natif comporte une section de parcours et une ligne par formation
achetée. Les formations restent aussi vendables seules. Chaque ligne conserve
sa version pédagogique et sa valeur contractuelle. Le total négocié est réparti
entre les lignes avant acceptation, dans une seule devise par offre.

Les montants peuvent être fixés au devis, sans liste de prix exhaustive ni
conversion automatique des tarifs MAD/EUR. Le mode de prix fixe existant reste
possible ; les documents historiques conservent ce mode. La nouvelle option
« Prix convenu au devis » permet la négociation explicite. Les montants nuls
peuvent représenter une prestation incluse ; ils ne sont jamais déduits d'un
acquis automatiquement. Une équivalence a un effet pédagogique ; son impact
commercial est convenu au cas par cas avant acceptation.

L'assistant propose toutes les formations, permet d'en décocher, choisit les
produits de service existants et prépare le devis. Il ne crée ni formation,
produit, réalisation, inscription, droit ou paiement. Les acomptes, factures,
avoirs, fiscalité et virements restent dans les circuits natifs existants.

## Groupe et droits

Le plafond du contrat porte sur les bénéficiaires distincts du parcours. Chaque
formation achetée dispose de son propre quota de places, répartissable entre
ses réalisations, sans multiplier le groupe. Dix bénéficiaires sur trois
formations peuvent donc avoir dix places par formation, sans devenir trente
bénéficiaires. Le groupe reste le même ; un bénéficiaire peut être dispensé
d’une formation sur la base d’acquis validés, sans y être réinscrit.
Les personnes déjà engagées sur une formation ne peuvent pas
être remplacées silencieusement pour recycler le quota du parcours.

Une nomination commerciale rattache l'inscription existante à l'étape du
parcours. Une acquisition antérieure complète peut être référencée au contrat,
sans nouvelle inscription, place ou progression. Les références commerciales
conservent auteur, date et retrait motivé. Les motifs et résultats pédagogiques
ne figurent pas sur le devis et restent réservés aux profils pédagogiques.

Acheter seulement une étape ne valide pas ses prérequis. Une étape obligatoire
non achetée doit être satisfaite par un acquis validé ou suivie séparément.
La confirmation de commande n'ouvre aucun accès ; les contrôles d'admission,
prérequis, capacité et autorisation commerciale restent applicables.

## Modifications et conservation

Après confirmation, la composition, l'effectif et les prix de l'offre sont
figés ; une modification contractuelle nécessite une révision explicite.
La copie native prépare un nouveau devis sans transférer les inscriptions
ni les droits. La régularisation du contrat antérieur reste manuelle.
Annulation, report et remplacement restent manuels et motivés. Les frais
éventuels suivent le devis accepté ; aucun avoir ni remboursement automatique.
Un remplaçant ne reçoit pas les résultats du participant précédent.

Le catalogue pédagogique reste indépendant des ventes. L'intégration étend
`training_management_sale`, réutilise les contacts, commandes, lignes, lots,
inscriptions et références de parcours ; aucun second registre de progression.

## Recette courte

1. Préparer un devis individuel complet, puis un devis de groupe limité à
   certaines formations ; vérifier produits, versions, prix, devise et PDF.
2. Négocier les montants, confirmer puis refuser leur modification directe.
   Tester facture, acompte et avoir natifs sans paiement ni envoi réel.
3. Pour deux bénéficiaires et deux formations, attribuer deux places par étape,
   puis refuser une troisième place ou un troisième bénéficiaire distinct.
4. Réutiliser un acquis avec la coordination : aucun doublon d'inscription,
   accès, présence ou progression ; le prix ne change pas automatiquement.
5. Vérifier les refus entre sociétés, participants, portefeuilles commerciaux
   et rôles ; le portail commercial ne reçoit aucun résultat pédagogique.
6. Répéter les actions et deux nominations concurrentes ; mettre à jour une
   base fictive existante et comparer les historiques.
