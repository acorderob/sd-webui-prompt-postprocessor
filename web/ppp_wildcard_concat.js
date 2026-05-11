import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "ACB.PPP.WildcardConcat",

    async nodeCreated(node) {
        if (node.comfyClass !== "ACBPPPWildcardConcat") return;

        const refreshWildcards = async () => {
            const filterWidget = node.widgets?.find((w) => w.name === "filter");
            if (!filterWidget) return;

            try {
                const resp = await api.fetchApi(
                    `/acb_ppp/wildcards?filter=${encodeURIComponent(filterWidget.value ?? "")}`
                );
                const data = await resp.json();
                const wildcards = data.wildcards ?? [];

                for (let i = 1; i <= 10; i++) {
                    const widget = node.widgets?.find((w) => w.name === `wildcard_${i}`);
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

        // Button to manually reload wildcards from disk
        node.addWidget("button", "Refresh 🔄", null, refreshWildcards, { serialize: false });

        // Auto-refresh all wildcard dropdowns when the filter value changes
        const filterWidget = node.widgets?.find((w) => w.name === "filter");
        if (filterWidget) {
            const origCallback = filterWidget.callback;
            filterWidget.callback = async function (...args) {
                if (origCallback) origCallback.apply(this, args);
                await refreshWildcards();
            };
        }
    },
});
