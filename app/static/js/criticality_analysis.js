// Variables globales para almacenar el último resultado
let ultimoReporte = '';

function formatearMonto(valor) {
    if (valor === null || valor === undefined || isNaN(valor)) return 'N/A';
    return '$ ' + valor.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Inicializar el análisis (se llama desde el template)
function initCriticalityAnalysis() {
    const calculateBtn = document.getElementById('calculateBtn');
    const exportBtn = document.getElementById('exportBtn');

    if (!calculateBtn) {
        console.error('Botón calcular no encontrado');
        return;
    }

    calculateBtn.addEventListener('click', function() {
        console.log('Botón calcular clickeado');

        // Obtener valores
        const cr = parseFloat(document.getElementById('cr').value) || 0;
        const cs = parseFloat(document.getElementById('cs').value) || 0;
        let rul = parseFloat(document.getElementById('rul').value) || 0;
        const newLife = parseFloat(document.getElementById('new_life').value) || 0;
        const funds = document.getElementById('funds').value;
        const risk = document.getElementById('risk').value;
        const umbralPorcentaje = parseFloat(document.getElementById('umbral').value) || 70;
        const umbralDecimal = umbralPorcentaje / 100;

        const criticality = equipmentData.criticality;
        const criticalityText = criticality === 'A' ? 'Crítico' : (criticality === 'B' ? 'Importante' : 'Prescindible');
        const availability = equipmentData.availability_level || 'No definida';
        const maintenanceModel = equipmentData.maintenance_model || 'No definido';
        const equipmentCost = equipmentData.equipment_cost_mxn;
        const repairCost = equipmentData.repair_cost_mxn;
        const downtimeCost = equipmentData.downtime_cost_mxn;

        // Validar RUL
        let rulEffective = rul;
        let obsolescencia = false;
        if (rulEffective <= 0) {
            obsolescencia = true;
            rulEffective = 0.001;
        }

        // Cálculo de CAR y CAS
        let car = null, cas = null;
        let carText = 'No se puede calcular (RUL no válido)';
        let casText = 'No se puede calcular (vida útil nueva no válida)';

        if (!obsolescencia && rulEffective > 0 && cr > 0) {
            car = cr / rulEffective;
            carText = formatearMonto(car) + ' / año';
        } else if (obsolescencia) {
            carText = 'Equipo obsoleto (vida útil superada) → CAR no aplicable';
        }

        if (newLife > 0 && cs > 0) {
            cas = cs / newLife;
            casText = formatearMonto(cas) + ' / año';
        }

        // Explicación de cálculos
        let explicacionCalculos = '';
        if (!obsolescencia && car !== null && cas !== null) {
            explicacionCalculos = `
EXPLICACIÓN DE CÁLCULOS:
• CAR (Costo Anualizado de Reparación) = CR / RUL = ${formatearMonto(cr)} / ${rul} años = ${carText}
  → Distribuye el costo de reparación entre los años de vida útil restante.

• CAS (Costo Anualizado de Sustitución) = CS / Vida útil nueva = ${formatearMonto(cs)} / ${newLife} años = ${casText}
  → Distribuye el costo del equipo nuevo entre toda su vida útil esperada.

• Umbral de sustitución: Si CR > ${umbralPorcentaje}% de CS, se recomienda sustituir.
  ${cr > cs * umbralDecimal ? `✓ Se cumple: ${formatearMonto(cr)} > ${umbralPorcentaje}% de ${formatearMonto(cs)}` : `✗ No se cumple: ${formatearMonto(cr)} ≤ ${umbralPorcentaje}% de ${formatearMonto(cs)}`}
`;
        }

        // Decisión económica (con umbral)
        let economicDecision = '';
        let economicColor = '';
        let umbralActivo = false;

        if (cs > 0 && cr > cs * umbralDecimal) {
            umbralActivo = true;
            economicDecision = `Sustitución por umbral (CR > ${umbralPorcentaje}% de CS)`;
            economicColor = 'danger';
        } else if (!obsolescencia && car !== null && cas !== null) {
            if (car < cas) {
                economicDecision = 'Reparar (CAR menor)';
                economicColor = 'success';
            } else if (cas < car) {
                economicDecision = 'Sustituir (CAS menor)';
                economicColor = 'danger';
            } else {
                economicDecision = 'Indiferente (CAR ≈ CAS)';
                economicColor = 'secondary';
            }
        } else if (obsolescencia) {
            economicDecision = 'Sustitución recomendada por obsolescencia';
            economicColor = 'danger';
        } else {
            economicDecision = 'Datos insuficientes para comparar';
            economicColor = 'secondary';
        }

        // Factores cualitativos y recomendación final
        let qualitativeRecommendation = '';
        let finalRecommendation = '';

        if (umbralActivo) {
            finalRecommendation = `✅ RECOMENDACIÓN: SUSTITUIR (CR > ${umbralPorcentaje}% de CS)`;
            qualitativeRecommendation = `⚠️ Umbral de sustitución activado (${umbralPorcentaje}%).`;
        } else if (criticality === 'A') {
            qualitativeRecommendation = '⚠️ Equipo CRÍTICO para la operación.';
            if (obsolescencia) {
                finalRecommendation = '✅ RECOMENDACIÓN: SUSTITUIR INMEDIATAMENTE (equipo obsoleto y crítico).';
            } else if (cas !== null && car !== null && cas < car) {
                finalRecommendation = '✅ RECOMENDACIÓN: SUSTITUIR (crítico + CAS menor).';
            } else {
                finalRecommendation = '⚠️ RECOMENDACIÓN: EVALUAR PROYECTO DE REEMPLAZO.';
            }
        } else if (criticality === 'B') {
            qualitativeRecommendation = '📌 Equipo IMPORTANTE.';
            if (obsolescencia) {
                finalRecommendation = '⚠️ RECOMENDACIÓN: PLANIFICAR SUSTITUCIÓN a mediano plazo.';
            } else if (risk === 'high') {
                qualitativeRecommendation += ' Alto riesgo de falla.';
                if (cas !== null && car !== null && cas < car) {
                    finalRecommendation = '✅ RECOMENDACIÓN: SUSTITUIR.';
                } else {
                    finalRecommendation = '⚠️ RECOMENDACIÓN: Reparar y monitorear.';
                }
            } else {
                qualitativeRecommendation += ' Bajo riesgo de falla.';
                if (car !== null && cas !== null && car < cas) {
                    finalRecommendation = '✅ RECOMENDACIÓN: REPARAR.';
                } else {
                    finalRecommendation = '📌 RECOMENDACIÓN: Reparar y mantener.';
                }
            }
        } else {
            qualitativeRecommendation = '🔧 Equipo PRESCINDIBLE.';
            if (obsolescencia) {
                finalRecommendation = '📌 RECOMENDACIÓN: Operar hasta falla (correctivo).';
            } else if (car !== null && cas !== null && car < cas) {
                finalRecommendation = '✅ RECOMENDACIÓN: REPARAR.';
            } else {
                finalRecommendation = '📌 RECOMENDACIÓN: Mantenimiento correctivo.';
            }
        }

        const fundsText = (funds === 'adequate') ? 'Fondos adecuados disponibles' : 'Fondos limitados';
        const fundsRecommendation = (funds === 'adequate') ? 'Se puede considerar inversión en sustitución.' : 'Priorizar reparaciones mientras se gestiona presupuesto.';

        // Generar reporte
        const fecha = new Date().toLocaleString('es-MX');
        const equipoInfo = `EQUIPO: ${equipmentData.code} - ${equipmentData.name}\nCriticidad: ${criticalityText}\nModelo: ${maintenanceModel}\nDisponibilidad: ${availability}`;
        const costosInfo = `COSTOS:\n• Costo equipo: ${formatearMonto(equipmentCost)}\n• Costo reparación (estimado): ${formatearMonto(repairCost)}\n• Valor hora parada: ${formatearMonto(downtimeCost)}\n• CR: ${formatearMonto(cr)}\n• CS: ${formatearMonto(cs)}\n• RUL: ${rul} años ${obsolescencia ? '(obsoleto)' : ''}\n• Vida útil nueva: ${newLife} años`;
        const analisisEconomico = `ANÁLISIS ECONÓMICO:\n• CAR: ${carText}\n• CAS: ${casText}\n• Decisión: ${economicDecision}`;
        const factoresCualitativos = `FACTORES CUALITATIVOS:\n• Criticidad: ${criticalityText}\n• Riesgo: ${risk === 'high' ? 'Alto' : 'Bajo'}\n• Fondos: ${fundsText} → ${fundsRecommendation}\n• ${qualitativeRecommendation}`;
        const recomendacionFinal = `RECOMENDACIÓN FINAL:\n${finalRecommendation}\n\nPlan de acción sugerido:\n${finalRecommendation.includes('SUSTITUIR') ? '- Cotizar nuevo equipo.\n- Programar instalación.\n- Gestionar presupuesto.' : '- Programar reparación.\n- Realizar seguimiento.\n- Actualizar plan preventivo.'}\n\nEste análisis es una guía. Decisión final debe ser aprobada por supervisor.`;

        const reporte = `
===========================================
 ANÁLISIS DE DECISIÓN REPARAR vs SUSTITUIR
         (Método CAR/CAS)
===========================================
Fecha: ${fecha}
${equipoInfo}
${costosInfo}
${analisisEconomico}
${explicacionCalculos}
${factoresCualitativos}
${recomendacionFinal}
===========================================
        `;
        ultimoReporte = reporte;

        // GRÁFICOS
        const ctxBar = document.getElementById('carCasChart').getContext('2d');
        if (window.carCasChartInstance) window.carCasChartInstance.destroy();
        let carValue = (car !== null && !obsolescencia) ? car : 0;
        let casValue = (cas !== null) ? cas : 0;
        window.carCasChartInstance = new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: ['Costo Anualizado (MXN/año)'],
                datasets: [
                    { label: 'Reparar (CAR)', data: [carValue], backgroundColor: 'rgba(54, 162, 235, 0.6)', borderColor: 'rgba(54, 162, 235, 1)', borderWidth: 1 },
                    { label: 'Sustituir (CAS)', data: [casValue], backgroundColor: 'rgba(255, 99, 132, 0.6)', borderColor: 'rgba(255, 99, 132, 1)', borderWidth: 1 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: { y: { beginAtZero: true, title: { display: true, text: 'MXN / año' } } },
                plugins: { tooltip: { callbacks: { label: (ctx) => ctx.dataset.label + ': ' + formatearMonto(ctx.raw) } } }
            }
        });

        let criticidadVal = criticality === 'A' ? 5 : (criticality === 'B' ? 3 : 1);
        let riesgoVal = risk === 'high' ? 5 : 1;
        let fondosVal = funds === 'adequate' ? 5 : 2;
        let obsolescenciaVal = obsolescencia ? 5 : 1;
        const ctxRadar = document.getElementById('factoresChart').getContext('2d');
        if (window.factoresChartInstance) window.factoresChartInstance.destroy();
        window.factoresChartInstance = new Chart(ctxRadar, {
            type: 'radar',
            data: {
                labels: ['Criticidad', 'Riesgo de falla', 'Fondos disponibles', 'Obsolescencia'],
                datasets: [{ label: 'Nivel de impacto (1=bajo, 5=alto)', data: [criticidadVal, riesgoVal, fondosVal, obsolescenciaVal], backgroundColor: 'rgba(255, 206, 86, 0.2)', borderColor: 'rgba(255, 206, 86, 1)', pointBackgroundColor: 'rgba(255, 206, 86, 1)', pointBorderColor: '#fff', borderWidth: 2 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: { r: { beginAtZero: true, max: 5, ticks: { stepSize: 1 } } },
                plugins: { tooltip: { callbacks: { label: (ctx) => ctx.label + ': ' + ctx.raw + ' / 5' } } }
            }
        });

        // Mostrar resultado
        const resultadoDiv = document.getElementById('resultadoAnalisis');
        const analisisTexto = document.getElementById('analisisTexto');
        analisisTexto.innerHTML = `
            <h6>Resultados del análisis económico:</h6>
            <ul>
                <li><strong>CAR:</strong> ${carText}</li>
                <li><strong>CAS:</strong> ${casText}</li>
                <li><strong>Decisión económica:</strong> <span class="text-${economicColor}">${economicDecision}</span></li>
            </ul>
            <h6 class="mt-3">Factores cualitativos:</h6>
            <ul>
                <li><strong>Criticidad:</strong> ${criticalityText}</li>
                <li><strong>Riesgo de falla:</strong> ${risk === 'high' ? 'Alto' : 'Bajo'}</li>
                <li><strong>Disponibilidad de fondos:</strong> ${fundsText}</li>
                <li>${qualitativeRecommendation}</li>
            </ul>
            <h6 class="mt-3 text-primary">Recomendación final:</h6>
            <p class="fw-bold">${finalRecommendation}</p>
            <hr>
            <button id="copyReportBtn" class="btn btn-sm btn-secondary">Copiar reporte completo</button>
            <small class="text-muted ms-2">El reporte detallado se puede copiar o guardar con el botón "Guardar análisis".</small>
        `;
        resultadoDiv.style.display = 'block';
        setTimeout(() => {
            if (window.carCasChartInstance) window.carCasChartInstance.resize();
            if (window.factoresChartInstance) window.factoresChartInstance.resize();
        }, 100);
        exportBtn.disabled = false;

        document.getElementById('copyReportBtn').addEventListener('click', () => {
            navigator.clipboard.writeText(ultimoReporte).then(() => alert('Reporte copiado al portapapeles'));
        });
    });

    exportBtn.addEventListener('click', () => {
        if (!ultimoReporte) return;
        const blob = new Blob([ultimoReporte], { type: 'text/plain;charset=utf-8' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `analisis_${equipmentData.code}_${new Date().toISOString().slice(0,19)}.txt`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    });
}