# Contrato: revisión del diff (HU-11-05)

## Pantalla (texto plano; el color solo lo añade `Style`)

```
== REVISIÓN DE CAMBIOS: TAREA-14 ==
2 archivos, +18 -3
  nuevo       +12  -0   src/auth.py
  modificado  +6   -3   tests/test_auth.py
Criterios objetivos: 2 de 2 cumplidos
  [x] 1 El email es obligatorio
  [?] 3 El mensaje de error es claro (pendiente de validación humana)
-- diff --
<hasta 200 líneas; «… N líneas más: elige 2 para verlo completo»>
 [1] aprobar y hacer commit  [2] ver diff completo  [3] rechazar con motivo
 [4 N] confirmar criterio N   [5 N] rechazar criterio N
opción>
```

## Entradas válidas
`1`, `2`, `3`, `4 N`, `5 N` (N de un criterio semántico pendiente). `/salir` o fin de entrada = sin decisión. Tres entradas inválidas seguidas = sin decisión. El texto inválido no se repite.

## Resultados
- Aprobar: `Commit hecho: <id corto>` o `No se pudo hacer el commit: <línea acotada>`.
- Rechazar: el agente recibe `[review_rejected] The user rejected the changes of this task.` y, con motivo válido, ` Reason: '<motivo>'`. Rechazar criterio: `[criterion_rejected] Criterion N ("<descripción>") was rejected by the user.` más el motivo.

## Evento
`criterion_verified` con `status: "confirmado_humano"`, `met: true`, `exit_code: null`, `program: null`. Sin tipos de evento nuevos.
