# Strategy development

Strategies are versioned plugins with an ID, version and declared data requirements. Changing behavior requires a new version/fingerprint. Strategy removal or disabling does not erase historical results.

Raw market-data schema is not redesigned for individual strategies; derived features should be independently versioned.
