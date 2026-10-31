*** Settings ***
Documentation    Cycle de vie technique du navigateur ; aucune règle métier.
Library    Browser    timeout=20s

*** Variables ***
${BASE_URL}    %{TM_BASE_URL=http://127.0.0.1:18099}
${HEADLESS}    ${True}

*** Keywords ***
Ouvrir une session isolée
    [Documentation]    Crée un navigateur et un contexte vierges pour un seul test.
    New Browser    chromium    headless=${HEADLESS}
    New Context    acceptDownloads=${True}    locale=en-US
    New Page

Terminer le parcours
    [Documentation]    Conserve une capture si le test échoue et ferme toujours le navigateur.
    TRY
        Run Keyword If Test Failed    Take Screenshot
    FINALLY
        Close Browser    ALL
    END
