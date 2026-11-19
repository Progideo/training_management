# Catalogue public — qualité (lot 5)

Suite des lots [2](catalogue-public-lot2.md), [3](catalogue-public-lot3.md) et
[4](catalogue-public-lot4.md), sur la page catalogue et la page formation.

## Accessibilité

| Critère | Mesure |
| --- | --- |
| Contraste | Le texte secondaire suit la couleur du corps de texte : avec le thème NeoPro, le gris secondaire à 75 % d'opacité donnait environ 4:1 sur blanc et 3,5:1 sur le bandeau gris (mesuré sur le dev le 19 nov. 2026). Les libellés clairs du bandeau de la fiche passent en blanc. |
| Cibles | Boutons, onglets, sommaire, formats, filtres, tris et pagination : 44 px minimum. |
| Focus | Contour de 3 px (couleur d'accent) sur liens, boutons, champs, résumés et panneaux ; contour de la carte entière quand son lien a le focus. |
| Libellés | Formats non disponibles annoncés en toutes lettres ; nombre de formations des filtres annoncé ; filtres mobiles dans un bouton « Filtrer (n) ». |
| Onglets | Liste d'onglets nommée, panneaux `tabpanel` focalisables reliés à leur onglet ; navigation clavier Bootstrap. |
| SEO | Balise `meta description` de la fiche : l'accroche, coupée vers 160 caractères. |

## Tests ajoutés

- Fiche sans session, sans prix ni avis : « Sur devis », « Aucune session programmée », alerte de nouvelles dates, pas d'avis ni de lien d'ancre vers eux, onglets accessibles, ancres valides.
- Filtres combinés (recherche, domaine, niveau, durée, certifiante) : résultat, filtres actifs, compteurs calculés en gardant les autres filtres, libellés accessibles, panneau mobile.
- Fuseau horaire : la prochaine session est datée dans le fuseau de la session (23 h 30 UTC = lendemain à Tokyo).

## Mesure de performance

Lighthouse ne peut pas être lancé depuis l'environnement de développement de
l'assistant. Constat de référence sur dev.neoproacademy.ma (code actuel, avant
déploiement des lots 2 à 5), mesuré dans le navigateur le 19 nov. 2026 :

| Page | Éléments DOM | Requêtes | Champs sans libellé | Meta description |
| --- | --- | --- | --- | --- |
| `/formations` | 530 | 7 | 2 (recherche de l'en-tête du thème) | absente |
| `/formations/catalogue/212` | 440 | 7 | 2 (idem) | absente |

Les ressources du site sont servies **sans compression** par nginx (CSS 1,2 Mo et
JavaScript 3,9 Mo transférés tels quels) : c'est le premier gain de performance
attendu, à traiter dans la configuration du serveur, hors de ces modules. Les deux
champs de recherche de l'en-tête appartiennent au thème.

Mesure après déploiement : lancer Lighthouse (mobile) sur les deux pages et
comparer à ce constat.
