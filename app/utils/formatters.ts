/**
 * Slingshot Intelligent Price Formatter
 * Adjusts precision based on asset value for maximum readability.
 */
export function formatPrice(price: number | null | undefined): string {
    if (price == null || isNaN(price)) return '—';
    
    // Configuración de precisión dinámica
    let minDecimals = 2;
    let maxDecimals = 2;

    if (price < 0.001) {
        minDecimals = 8;
        maxDecimals = 8;
    } else if (price < 0.1) {
        minDecimals = 6;
        maxDecimals = 6;
    } else if (price < 2) {
        minDecimals = 4;
        maxDecimals = 4;
    } else if (price < 100) {
        minDecimals = 2;
        maxDecimals = 4;
    } else {
        minDecimals = 2;
        maxDecimals = 2;
    }

    return price.toLocaleString('en-US', {
        minimumFractionDigits: minDecimals,
        maximumFractionDigits: maxDecimals,
    });
}

/**
 * Formats values as currency ($)
 */
export function formatCurrency(price: number | null | undefined): string {
    const val = formatPrice(price);
    if (val === '—') return val;
    return '$' + val;
}
