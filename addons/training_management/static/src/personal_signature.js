import { Component, proxy, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { NameAndSignature } from "@web/core/signature/name_and_signature";

export class PersonalSignature extends Component {
    static template = "training_management.PersonalSignature";
    static components = { NameAndSignature };
    rootRef = signal.ref();
    setup() {
        this.signature = proxy({ name: "", isSignatureEmpty: true, getSignatureImage: () => "" });
        this.signatureProps = {
            signature: this.signature,
            mode: "draw",
            noInputName: true,
            onSignatureChange: () => this.updateDrawing(),
        };
    }
    updateDrawing() {
        const form = this.rootRef()?.closest("form");
        if (form) {
            form.querySelector("[name=drawing]").value = this.signature.isSignatureEmpty
                ? "" : this.signature.getSignatureImage().split(",")[1];
        }
    }
}
registry.category("public_components").add("training_management.PersonalSignature", PersonalSignature);
