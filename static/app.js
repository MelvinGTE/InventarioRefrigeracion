document.addEventListener('DOMContentLoaded', () => {
    // =========================================================
    // 1. VISTA PREVIA DE FOTO (Cargar / Editar Producto: Cámara y Galería)
    // =========================================================
    const fotoInput = document.getElementById('fotoInput');
    const fotoCamaraInput = document.getElementById('fotoCamaraInput');
    const btnAbrirCamara = document.getElementById('btnAbrirCamara');
    const btnAbrirGaleria = document.getElementById('btnAbrirGaleria');
    const fotoPreview = document.getElementById('fotoPreview');
    const photoPlaceholder = document.getElementById('photoPlaceholder');
    const photoPreviewContainer = document.getElementById('photoPreviewContainer');
    const fotoFileName = document.getElementById('fotoFileName');
    const btnQuitarFoto = document.getElementById('btnQuitarFoto');
    const eliminarFotoCheck = document.getElementById('eliminarFotoCheck');

    if (btnAbrirCamara && fotoCamaraInput) {
        btnAbrirCamara.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fotoCamaraInput.value = '';
            fotoCamaraInput.click();
        });
    }

    if (btnAbrirGaleria && fotoInput) {
        btnAbrirGaleria.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fotoInput.click();
        });
    }

    if (fotoCamaraInput && fotoInput) {
        fotoCamaraInput.addEventListener('change', () => {
            if (fotoCamaraInput.files && fotoCamaraInput.files.length > 0) {
                const dt = new DataTransfer();
                dt.items.add(fotoCamaraInput.files[0]);
                fotoInput.files = dt.files;
                fotoInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    if (fotoInput && fotoPreview) {
        fotoInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                fotoPreview.src = URL.createObjectURL(file);
                fotoPreview.style.display = 'block';
                if (photoPlaceholder) photoPlaceholder.classList.add('hidden');
                if (photoPreviewContainer) photoPreviewContainer.classList.remove('hidden');
                if (fotoFileName) fotoFileName.textContent = file.name;
                if (eliminarFotoCheck) eliminarFotoCheck.checked = false;
            }
        });

        if (btnQuitarFoto) {
            btnQuitarFoto.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                fotoInput.value = '';
                if (fotoCamaraInput) fotoCamaraInput.value = '';
                fotoPreview.src = '';
                if (photoPreviewContainer) photoPreviewContainer.classList.add('hidden');
                if (photoPlaceholder) photoPlaceholder.classList.remove('hidden');
            });
        }
    }

    // Atajo F2 en PC para abrir Consulta Rápida de Precios
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F2') {
            const modalPrecios = document.getElementById('modalConsultaPrecios');
            if (modalPrecios) {
                e.preventDefault();
                modalPrecios.classList.remove('hidden');
                const input = modalPrecios.querySelector('input[type="search"]');
                if (input) input.focus();
            }
        }
    });

    // =========================================================
    // 2. DESCARGAR INVENTARIO (Buscador, Subtotales y Filas)
    // =========================================================
    const listaDescarga = document.getElementById('listaDescarga');
    const btnAgregarDescarga = document.getElementById('btnAgregarDescarga');
    const totalDescargaEl = document.getElementById('totalDescarga');
    const catalogoOptions = Array.from(document.querySelectorAll('#catalogoRepuestos option'));

    // Mostrar/ocultar nombre manual si selecciona cliente registrado
    const clienteSelect = document.getElementById('cliente_id');
    const grupoClienteManual = document.getElementById('grupoClienteManual');
    if (clienteSelect && grupoClienteManual) {
        clienteSelect.addEventListener('change', () => {
            grupoClienteManual.style.display = clienteSelect.value ? 'none' : 'flex';
        });
    }

    const recalcularDescarga = () => {
        if (!listaDescarga || !totalDescargaEl) return;
        let totalGeneral = 0;

        listaDescarga.querySelectorAll('.item-row').forEach((row) => {
            const inputBuscar = row.querySelector('.input-buscar-repuesto');
            const hiddenId = row.querySelector('.hidden-producto-id');
            const inputCant = row.querySelector('.input-cant-descarga');
            const subtotalEl = row.querySelector('.subtotal-display');
            const stockHint = row.querySelector('.stock-hint');

            if (!inputBuscar || !hiddenId || !inputCant) return;

            const textoBuscado = inputBuscar.value.trim().toLowerCase();
            const match = catalogoOptions.find(
                (opt) => opt.value.trim().toLowerCase() === textoBuscado
            );

            if (match) {
                const precioRaw = (match.dataset.precio || '0').replace(',', '.');
                const precio = parseFloat(precioRaw) || 0;
                const stock = parseInt(match.dataset.stock, 10) || 0;
                const cant = parseInt(inputCant.value, 10) || 0;

                hiddenId.value = match.dataset.id;
                inputCant.max = stock;
                stockHint.textContent = `Disp: ${stock} uds. • Precio: Q ${precio.toFixed(2)}`;
                stockHint.style.color = cant > stock ? 'var(--danger)' : 'var(--primary)';

                const subtotal = cant * precio;
                subtotalEl.textContent = `Q ${subtotal.toFixed(2)}`;
                totalGeneral += subtotal;
            } else {
                hiddenId.value = '';
                stockHint.textContent = textoBuscado ? 'Selecciona un repuesto de la lista' : '';
                stockHint.style.color = 'var(--warning)';
                subtotalEl.textContent = 'Q 0.00';
            }
        });

        totalDescargaEl.textContent = `Q ${totalGeneral.toFixed(2)}`;
    };

    if (listaDescarga && btnAgregarDescarga) {
        listaDescarga.addEventListener('input', recalcularDescarga);
        listaDescarga.addEventListener('change', recalcularDescarga);

        btnAgregarDescarga.addEventListener('click', (e) => {
            e.preventDefault();
            const firstRow = listaDescarga.querySelector('.item-row');
            const clone = firstRow.cloneNode(true);

            clone.querySelector('.input-buscar-repuesto').value = '';
            clone.querySelector('.hidden-producto-id').value = '';
            clone.querySelector('.input-cant-descarga').value = 1;
            clone.querySelector('.subtotal-display').textContent = 'Q 0.00';
            clone.querySelector('.stock-hint').textContent = '';

            listaDescarga.appendChild(clone);
            clone.querySelector('.input-buscar-repuesto').focus();
        });

        listaDescarga.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.btn-remove-row');
            if (removeBtn) {
                if (listaDescarga.querySelectorAll('.item-row').length > 1) {
                    removeBtn.closest('.item-row').remove();
                    recalcularDescarga();
                }
            }
        });

        const descargaForm = document.getElementById('descargaForm');
        if (descargaForm) {
            descargaForm.addEventListener('submit', (e) => {
                let valido = true;
                listaDescarga.querySelectorAll('.item-row').forEach((row) => {
                    if (!row.querySelector('.hidden-producto-id').value) {
                        valido = false;
                        row.querySelector('.input-buscar-repuesto').focus();
                    }
                });
                if (!valido) {
                    e.preventDefault();
                    alert('Selecciona un repuesto válido de la lista desplegable en cada fila.');
                }
            });
        }
    }

    // =========================================================
    // 3. COTIZACIONES PDF (Buscador, Subtotales y Filas)
    // =========================================================
    const listaCotizacion = document.getElementById('listaCotizacion');
    const btnAgregarCotizacion = document.getElementById('btnAgregarCotizacion');
    const totalCotizacionEl = document.getElementById('totalCotizacion');
    const catalogoCotOptions = Array.from(document.querySelectorAll('#catalogoCotizacion option'));

    const cotClienteSelect = document.getElementById('cot_cliente_id');
    const grupoCotClienteManual = document.getElementById('grupoCotClienteManual');
    if (cotClienteSelect && grupoCotClienteManual) {
        cotClienteSelect.addEventListener('change', () => {
            grupoCotClienteManual.style.display = cotClienteSelect.value ? 'none' : 'flex';
        });
    }

    const renumerarItemsCotizacion = () => {
        if (!listaCotizacion) return;
        listaCotizacion.querySelectorAll('.cot-row').forEach((row, index) => {
            const badge = row.querySelector('.item-index-badge');
            if (badge) badge.textContent = `Ítem #${index + 1}`;
        });
    };

    const calcularTotalCotizacion = () => {
        if (!listaCotizacion || !totalCotizacionEl) return;
        let total = 0;
        listaCotizacion.querySelectorAll('.cot-row').forEach((row) => {
            const cant = parseFloat(row.querySelector('.input-cant-cot').value) || 0;
            const precio = parseFloat(row.querySelector('.input-precio-cot').value) || 0;
            const subtotal = cant * precio;
            const subDisplay = row.querySelector('.cot-subtotal-display');
            if (subDisplay) subDisplay.textContent = `Q ${subtotal.toFixed(2)}`;
            total += subtotal;
        });
        totalCotizacionEl.textContent = `Q ${total.toFixed(2)}`;
    };

    if (listaCotizacion && btnAgregarCotizacion) {
        // Autocompletar precio, stock y descripción al elegir del catálogo
        listaCotizacion.addEventListener('input', (e) => {
            if (e.target.classList.contains('input-buscar-cot')) {
                const row = e.target.closest('.cot-row');
                const hiddenId = row.querySelector('.hidden-prod-cot');
                const stockHint = row.querySelector('.cot-stock-hint');
                const texto = e.target.value.trim().toLowerCase();

                const match = catalogoCotOptions.find(
                    (opt) => opt.value.trim().toLowerCase() === texto
                );

                if (match) {
                    const precioClean = (match.dataset.precio || '0').replace(',', '.');
                    const stock = parseInt(match.dataset.stock, 10) || 0;
                    hiddenId.value = match.dataset.id;
                    row.querySelector('.input-precio-cot').value = precioClean;
                    if (!row.querySelector('.input-desc-cot').value.trim()) {
                        row.querySelector('.input-desc-cot').value = match.dataset.desc || '';
                    }
                    stockHint.textContent = stock > 0
                        ? `En bodega: ${stock} uds.`
                        : 'Sin stock en bodega (bajo pedido)';
                    stockHint.style.color = stock > 0 ? 'var(--primary)' : 'var(--warning)';
                } else {
                    hiddenId.value = '';
                    stockHint.textContent = texto ? 'Servicio técnico / ítem personalizado' : '';
                    stockHint.style.color = 'var(--slate-600)';
                }
            }
            calcularTotalCotizacion();
        });

        btnAgregarCotizacion.addEventListener('click', (e) => {
            e.preventDefault();
            const firstRow = listaCotizacion.querySelector('.cot-row');
            const clone = firstRow.cloneNode(true);

            clone.querySelector('.input-buscar-cot').value = '';
            clone.querySelector('.hidden-prod-cot').value = '';
            clone.querySelector('.cot-stock-hint').textContent = '';
            clone.querySelector('.input-cant-cot').value = 1;
            clone.querySelector('.input-precio-cot').value = '0.00';
            clone.querySelector('.cot-subtotal-display').textContent = 'Q 0.00';
            clone.querySelector('.input-desc-cot').value = '';

            listaCotizacion.appendChild(clone);
            renumerarItemsCotizacion();
            clone.querySelector('.input-buscar-cot').focus();
        });

        listaCotizacion.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.btn-remove-cot');
            if (removeBtn) {
                if (listaCotizacion.querySelectorAll('.cot-row').length > 1) {
                    removeBtn.closest('.cot-row').remove();
                    renumerarItemsCotizacion();
                    calcularTotalCotizacion();
                }
            }
        });
    }

    // =========================================================
    // 4. BUSCADOR INSTANTÁNEO EN TABLAS
    // =========================================================
    const normalizeText = (str) =>
        str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

    document.querySelectorAll('[data-table-filter]').forEach((input) => {
        const tableId = input.dataset.tableFilter;
        const table = document.getElementById(tableId);
        const clearBtn = input.parentElement.querySelector('.search-clear-btn');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        const colCount = table.querySelectorAll('thead th').length;

        const noMatchRow = document.createElement('tr');
        noMatchRow.style.display = 'none';
        noMatchRow.innerHTML = `<td colspan="${colCount}" style="text-align: center; color: var(--slate-400); padding: 1.25rem;">No se encontraron coincidencias para tu búsqueda.</td>`;
        tbody.appendChild(noMatchRow);

        const filterRows = () => {
            const query = normalizeText(input.value.trim());
            if (clearBtn) {
                clearBtn.style.display = query.length > 0 ? 'flex' : 'none';
            }

            let visibleCount = 0;
            tbody.querySelectorAll(':scope > tr').forEach((row) => {
                if (row === noMatchRow || row.classList.contains('empty-row') || row.id.startsWith('detalleCot')) return;
                const rowText = normalizeText(row.textContent);
                const matches = rowText.includes(query);
                row.style.display = matches ? '' : 'none';
                if (!matches) {
                    const nextDetail = row.nextElementSibling;
                    if (nextDetail && nextDetail.id.startsWith('detalleCot')) {
                        nextDetail.classList.add('hidden');
                    }
                }
                if (matches) visibleCount++;
            });
            noMatchRow.style.display = visibleCount === 0 && query.length > 0 ? '' : 'none';
        };

        input.addEventListener('input', filterRows);

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                input.value = '';
                filterRows();
                input.focus();
            });
        }
    });

    // =========================================================
    // 5. PANELES DESPLEGABLES (Clientes / Nueva Orden Técnica)
    // =========================================================
    document.querySelectorAll('[data-toggle-panel]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.togglePanel;
            const targetPanel = document.getElementById(targetId);
            if (!targetPanel) return;

            ['panelNuevoCliente', 'panelNuevaOrden'].forEach((id) => {
                if (id !== targetId) {
                    const other = document.getElementById(id);
                    if (other) other.classList.add('hidden');
                }
            });

            targetPanel.classList.toggle('hidden');
            if (!targetPanel.classList.contains('hidden')) {
                const firstInput = targetPanel.querySelector('input, select');
                if (firstInput) firstInput.focus();
            }
        });
    });

    // =========================================================
    // 6. CARGA DE REPUESTOS Y SERVICIO TÉCNICO EN ÓRDENES
    // =========================================================
    document.querySelectorAll('[data-toggle-srv]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const panel = document.getElementById(btn.dataset.toggleSrv);
            if (panel) {
                panel.classList.toggle('hidden');
                if (!panel.classList.contains('hidden')) {
                    const input = panel.querySelector('.srv-input-buscar');
                    if (input) input.focus();
                }
            }
        });
    });

    const catalogoSrvOptions = Array.from(document.querySelectorAll('#catalogoServicioRepuestos option'));

    document.querySelectorAll('.srv-repuestos-form').forEach((form) => {
        const lista = form.querySelector('.srv-lista-repuestos');
        const btnAdd = form.querySelector('.srv-btn-add');
        const totalDisplay = form.querySelector('.srv-total-display');
        const inputManoObra = form.querySelector('.srv-input-mano-obra');

        const recalcularOrden = () => {
            let total = 0;
            lista.querySelectorAll('.srv-item-row').forEach((row) => {
                const inputBuscar = row.querySelector('.srv-input-buscar');
                const hiddenId = row.querySelector('.srv-hidden-id');
                const inputCant = row.querySelector('.srv-input-cant');
                const subDisplay = row.querySelector('.srv-subtotal-display');
                const hint = row.querySelector('.srv-stock-hint');

                const texto = inputBuscar.value.trim().toLowerCase();
                const match = catalogoSrvOptions.find((opt) => opt.value.trim().toLowerCase() === texto);

                if (match) {
                    const precio = parseFloat((match.dataset.precio || '0').replace(',', '.')) || 0;
                    const stock = parseInt(match.dataset.stock, 10) || 0;
                    const cant = parseInt(inputCant.value, 10) || 0;

                    hiddenId.value = match.dataset.id;
                    inputCant.max = stock;
                    hint.textContent = `Disp: ${stock} uds. • Q ${precio.toFixed(2)}`;
                    hint.style.color = cant > stock ? 'var(--danger)' : 'var(--primary)';

                    const sub = cant * precio;
                    subDisplay.textContent = `Q ${sub.toFixed(2)}`;
                    total += sub;
                } else {
                    hiddenId.value = '';
                    hint.textContent = texto ? 'Elige un repuesto de la lista' : '';
                    hint.style.color = 'var(--warning)';
                    subDisplay.textContent = 'Q 0.00';
                }
            });

            const servicioTecnico = inputManoObra ? (parseFloat((inputManoObra.value || '0').replace(',', '.')) || 0) : 0;
            totalDisplay.textContent = `Q ${(total + servicioTecnico).toFixed(2)}`;
        };

        lista.addEventListener('input', recalcularOrden);
        lista.addEventListener('change', recalcularOrden);
        if (inputManoObra) inputManoObra.addEventListener('input', recalcularOrden);

        btnAdd.addEventListener('click', (e) => {
            e.preventDefault();
            const firstRow = lista.querySelector('.srv-item-row');
            const clone = firstRow.cloneNode(true);
            clone.querySelector('.srv-input-buscar').value = '';
            clone.querySelector('.srv-hidden-id').value = '';
            clone.querySelector('.srv-input-cant').value = 1;
            clone.querySelector('.srv-subtotal-display').textContent = 'Q 0.00';
            clone.querySelector('.srv-stock-hint').textContent = '';
            lista.appendChild(clone);
            clone.querySelector('.srv-input-buscar').focus();
        });

        lista.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.srv-btn-remove');
            if (removeBtn && lista.querySelectorAll('.srv-item-row').length > 1) {
                removeBtn.closest('.srv-item-row').remove();
                recalcularOrden();
            }
        });

        // Permite guardar solo servicio técnico, solo repuestos, o ambos
        form.addEventListener('submit', (e) => {
            let valido = true;
            lista.querySelectorAll('.srv-item-row').forEach((row) => {
                const texto = row.querySelector('.srv-input-buscar').value.trim();
                const idVal = row.querySelector('.srv-hidden-id').value;
                if (texto && !idVal) {
                    valido = false;
                    row.querySelector('.srv-input-buscar').focus();
                }
            });
            if (!valido) {
                e.preventDefault();
                alert('Selecciona un repuesto válido de la lista o deja el campo vacío si solo cobrarás servicio técnico.');
            }
        });
    });

    // =========================================================
    // 7. BUSCADOR INTELIGENTE DE CLIENTES (Global)
    // =========================================================
    const catalogoClientesOptions = Array.from(document.querySelectorAll('#catalogoClientes option'));

    document.querySelectorAll('.input-buscar-cliente').forEach((input) => {
        const hiddenInput = document.getElementById(input.dataset.hiddenTarget);
        const hintEl = document.getElementById(input.dataset.hintTarget);
        const manualGroup = input.dataset.manualToggle
            ? document.getElementById(input.dataset.manualToggle)
            : null;

        const syncCliente = () => {
            const texto = input.value.trim().toLowerCase();
            const match = catalogoClientesOptions.find(
                (opt) => opt.value.trim().toLowerCase() === texto
            );

            if (match) {
                hiddenInput.value = match.dataset.id;
                if (hintEl) {
                    hintEl.textContent = `Dirección: ${match.dataset.dir}`;
                    hintEl.style.color = 'var(--primary)';
                }
                if (manualGroup) manualGroup.style.display = 'none';
            } else {
                hiddenInput.value = '';
                if (hintEl) {
                    hintEl.textContent = texto ? 'Selecciona un cliente válido de la lista' : '';
                    hintEl.style.color = 'var(--warning)';
                }
                if (manualGroup) manualGroup.style.display = 'flex';
            }
        };

        input.addEventListener('input', syncCliente);
        input.addEventListener('change', syncCliente);

        // Validar si el campo es obligatorio (ej. Nueva Orden Técnica)
        const parentForm = input.closest('form');
        if (parentForm && input.required) {
            parentForm.addEventListener('submit', (e) => {
                if (!hiddenInput.value) {
                    e.preventDefault();
                    input.focus();
                    alert('Por favor selecciona un cliente registrado de las sugerencias.');
                }
            });
        }
    });

    // =========================================================
    // 8. PESTAÑAS (TABS) Y MODALES FLOTANTES
    // =========================================================
    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach((p) => p.classList.add('hidden'));

            btn.classList.add('active');
            const target = document.getElementById(btn.dataset.tabTarget);
            if (target) target.classList.remove('hidden');
        });
    });

    // Abrir modales (+ Nuevo Cliente / + Nueva Orden Técnica)
    document.querySelectorAll('[data-open-modal]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const modal = document.getElementById(btn.dataset.openModal);
            if (modal) {
                modal.classList.remove('hidden');
                const firstInput = modal.querySelector('input:not([type="hidden"])');
                if (firstInput) firstInput.focus();
            }
        });
    });

    // Cerrar modales con botón, clic en fondo oscuro o tecla ESC
    document.querySelectorAll('[data-close-modal]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const modal = document.getElementById(btn.dataset.closeModal);
            if (modal) modal.classList.add('hidden');
        });
    });

    document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) backdrop.classList.add('hidden');
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-backdrop').forEach((m) => m.classList.add('hidden'));
        }
    });

    // Filtro rápido en vivo para tarjetas de Órdenes de Taller
    const filtroOrdenesInput = document.getElementById('filtroOrdenesInput');
    if (filtroOrdenesInput) {
        filtroOrdenesInput.addEventListener('input', () => {
            const q = normalizeText(filtroOrdenesInput.value.trim());
            document.querySelectorAll('#listaOrdenesTaller .orden-card').forEach((card) => {
                card.style.display = normalizeText(card.textContent).includes(q) ? '' : 'none';
            });
        });
    }

    // =========================================================
    // 9. VALIDACIÓN TELÉFONO 8 DÍGITOS Y MODAL EDITAR CLIENTE
    // =========================================================
    document.querySelectorAll('.input-telefono-8').forEach((input) => {
        input.addEventListener('input', () => {
            input.value = input.value.replace(/\D/g, '').slice(0, 8);
        });
    });

    const modalEditarCliente = document.getElementById('modalEditarCliente');
    const formEditarCliente = document.getElementById('formEditarCliente');
    if (modalEditarCliente && formEditarCliente) {
        document.querySelectorAll('.btn-editar-cliente').forEach((btn) => {
            btn.addEventListener('click', () => {
                formEditarCliente.action = `/inventario/clientes/${btn.dataset.id}/editar/`;
                document.getElementById('edit_nombre_cliente').value = btn.dataset.nombre || '';
                document.getElementById('edit_telefono_cliente').value = (btn.dataset.telefono || '').replace(/\D/g, '').slice(0, 8);
                document.getElementById('edit_direccion_cliente').value = btn.dataset.direccion || '';
                modalEditarCliente.classList.remove('hidden');
                document.getElementById('edit_nombre_cliente').focus();
            });
        });
    }

    // =========================================================
    // 10. COTIZADOR EDITABLE DE ORDEN DE SERVICIO TÉCNICO
    // =========================================================
    const formCotizarOrden = document.getElementById('formCotizarOrden');
    const listaItemsOrdenCot = document.getElementById('listaItemsOrdenCot');
    const totalOrdenCot = document.getElementById('totalOrdenCot');
    const btnAddLineaOrdenCot = document.getElementById('btnAddLineaOrdenCot');
    const inputManoObraCot = document.getElementById('costo_mano_obra');

    if (formCotizarOrden && listaItemsOrdenCot) {
        const opcionesOrdenCot = Array.from(document.querySelectorAll('#catalogoCotOrden option'));

        const recalcularOrdenCot = () => {
            let total = 0;

            listaItemsOrdenCot.querySelectorAll('.orden-cot-row').forEach((row) => {
                const descInput = row.querySelector('.oc-input-desc');
                const hiddenProd = row.querySelector('.oc-hidden-prod');
                const hiddenTipo = row.querySelector('.oc-hidden-tipo');
                const cantInput = row.querySelector('.oc-input-cant');
                const precioInput = row.querySelector('.oc-input-precio');
                const subDisplay = row.querySelector('.oc-subtotal');
                const hint = row.querySelector('.oc-hint');

                const texto = descInput.value.trim().toLowerCase();
                const match = opcionesOrdenCot.find((opt) => opt.value.trim().toLowerCase() === texto);

                if (match) {
                    if (hiddenProd.value !== match.dataset.id) {
                        hiddenProd.value = match.dataset.id;
                        precioInput.value = parseFloat((match.dataset.precio || '0').replace(',', '.')).toFixed(2);
                    }
                    if (hiddenTipo) hiddenTipo.value = 'repuesto';
                    hint.textContent = `Repuesto en inventario (Stock: ${match.dataset.stock})`;
                    hint.style.color = 'var(--primary)';
                } else {
                    hiddenProd.value = '';
                    if (hiddenTipo) hiddenTipo.value = 'mano_obra';
                    hint.textContent = texto ? 'Servicio técnico especializado' : '';
                    hint.style.color = 'var(--slate-600)';
                }

                const cant = parseInt(cantInput.value, 10) || 0;
                const precio = parseFloat((precioInput.value || '0').replace(',', '.')) || 0;
                const sub = cant * precio;
                subDisplay.textContent = `Q ${sub.toFixed(2)}`;
                total += sub;
            });

            const servicioTecnicoBase = inputManoObraCot
                ? (parseFloat((inputManoObraCot.value || '0').replace(',', '.')) || 0)
                : 0;
            total += servicioTecnicoBase;

            if (totalOrdenCot) {
                totalOrdenCot.textContent = `Q ${total.toFixed(2)}`;
            }
        };

        listaItemsOrdenCot.addEventListener('input', recalcularOrdenCot);
        listaItemsOrdenCot.addEventListener('change', recalcularOrdenCot);

        if (inputManoObraCot) {
            inputManoObraCot.addEventListener('input', recalcularOrdenCot);
            inputManoObraCot.addEventListener('change', recalcularOrdenCot);
        }

        if (btnAddLineaOrdenCot) {
            btnAddLineaOrdenCot.addEventListener('click', () => {
                const firstRow = listaItemsOrdenCot.querySelector('.orden-cot-row');
                const clone = firstRow.cloneNode(true);
                clone.querySelector('.oc-input-desc').value = '';
                clone.querySelector('.oc-hidden-prod').value = '';
                const tipoHidden = clone.querySelector('.oc-hidden-tipo');
                if (tipoHidden) tipoHidden.value = 'repuesto';
                clone.querySelector('.oc-input-cant').value = 1;
                clone.querySelector('.oc-input-precio').value = '0.00';
                clone.querySelector('.oc-subtotal').textContent = 'Q 0.00';
                clone.querySelector('.oc-hint').textContent = '';
                listaItemsOrdenCot.appendChild(clone);
                clone.querySelector('.oc-input-desc').focus();
            });
        }

        listaItemsOrdenCot.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.oc-btn-remove');
            if (removeBtn && listaItemsOrdenCot.querySelectorAll('.orden-cot-row').length > 1) {
                removeBtn.closest('.orden-cot-row').remove();
                recalcularOrdenCot();
            }
        });

        recalcularOrdenCot();
    }

    // =========================================================
    // 11. VISOR DE ZOOM PARA FOTOGRAFÍAS DE REPUESTOS
    // =========================================================
    const modalZoomFoto = document.getElementById('modalZoomFoto');
    const zoomFotoImg = document.getElementById('zoomFotoImg');
    const zoomFotoTitulo = document.getElementById('zoomFotoTitulo');

    if (modalZoomFoto && zoomFotoImg) {
        document.addEventListener('click', (e) => {
            const thumb = e.target.closest('[data-zoom-img]');
            if (thumb) {
                e.stopPropagation();
                zoomFotoImg.src = thumb.dataset.zoomImg;
                if (zoomFotoTitulo) {
                    zoomFotoTitulo.textContent = thumb.dataset.zoomTitle || 'Fotografía del repuesto';
                }
                modalZoomFoto.classList.remove('hidden');
            }
        });
    }
});