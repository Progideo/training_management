*** Settings ***
Documentation    Liste et formulaire natifs Odoo des catégories de formation.
Resource    ../browser.resource

*** Variables ***
${CATEGORY_CREATE}    .o_list_button_add
${CATEGORY_NAME_INPUT}    .o_field_widget[name="name"] input
${CATEGORY_SAVE}    .o_form_button_save

*** Keywords ***
Ouvrir la liste des catégories
    [Arguments]    ${action_id}
    Go To    ${BASE_URL}/odoo/action-${action_id}
    Wait For Elements State    ${CATEGORY_CREATE}    visible

Créer une catégorie dans le formulaire
    [Arguments]    ${name}
    Click    ${CATEGORY_CREATE}
    Fill Text    ${CATEGORY_NAME_INPUT}    ${name}
    Click    ${CATEGORY_SAVE}
    Wait For Elements State    ${CATEGORY_SAVE}    hidden

Recharger la catégorie
    Reload
    Wait For Elements State    ${CATEGORY_NAME_INPUT}    visible

Lire le nom de la catégorie
    ${name}=    Get Property    ${CATEGORY_NAME_INPUT}    value
    RETURN    ${name}
