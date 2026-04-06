import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "ACB.PPP.WildcardConcat",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ACBPPPWildcardConcat") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const self = this;

            const refreshWildcards = async () => {
                const filterWidget = self.widgets?.find((w) => w.name === "filter");
                if (!filterWidget) return;

                try {
                    const resp = await api.fetchApi(
                        `/acb_ppp/wildcards?filter=${encodeURIComponent(filterWidget.value ?? "")}`
                    );
                    const data = await resp.json();
                    const wildcards = data.wildcards ?? [];

                    for (let i = 1; i <= 10; i++) {
                        const widget = self.widgets?.find((w) => w.name === `wildcard_${i}`);
                        if (widget) {
                            const current = widget.value;
                            widget.options.values = wildcards;
                            widget.value = wildcards.includes(current)
                                ? current
                                : wildcards[0] ?? "(none)";
                        }
                    }

                    app.graph.setDirtyCanvas(true, false);
                } catch (err) {
                    console.error("[ACB PPP] Failed to refresh wildcard list:", err);
                }
            };

            // Hook the filter widget so that committing a new value (Enter / blur)
            // immediately refreshes all 10 wildcard dropdowns without running the workflow.
            const filterWidget = this.widgets?.find((w) => w.name === "filter");
            if (filterWidget) {
                const origCallback = filterWidget.callback;
                filterWidget.callback = async function (...args) {
                    if (origCallback) origCallback.apply(this, args);
                    await refreshWildcards();
                };
            }

            return result;
        };
    },
});
