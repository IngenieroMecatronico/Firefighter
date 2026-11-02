
%% ============================================================
% ROBOTAT - TRAYECTORIA 2D CON HISTORIAL DE POSES
%
% Marker movil: 30
% Marker objetivo: 74
%
% MEJORAS:
% 1. Plano XY ampliado.
% 2. Ejes que se expanden automaticamente.
% 3. Posicion del Marker 74 actualizada continuamente.
% 4. Historial de poses semitransparentes.
% 5. Orientacion actual del Marker 30.
% 6. Registro de trayectoria en CSV y MAT.
%% ============================================================

clear;
clc;
close all;

%% CONFIGURACION

MARKER_MOVIL = 30;
MARKER_OBJETIVO = 74;

dt = 0.05;
TOLERANCIA = 0.10;

LONG_FLECHA = 0.10;

LARGO_ROBOT = 0.10;
ANCHO_ROBOT = 0.10;

DISTANCIA_POSE = 0.15;
ALPHA_HISTORIAL = 0.18;

OFFSET_ORIENTACION_DEG = 0;

% Rango inicial del plano XY
X_LIM_INICIAL = [-3 3];
Y_LIM_INICIAL = [-3 3];

% Margen para ampliar los ejes
MARGEN_EJES = 0.50;

% Historial del Marker 30
trayectoria_x = [];
trayectoria_y = [];
orientaciones_deg = [];
tiempos = [];

% Historial del Marker 74
objetivo_hist_x = [];
objetivo_hist_y = [];

robotat = [];
fig = [];

%% CONEXION ROBOTAT

disp("Conectando con Robotat...");

robotat = robotat_connect();

disp("Conexion establecida.");

%% CAPTURA Y GRAFICA 2D

try

    %% LEER POSICIONES INICIALES

    pose30 = robotat_get_pose( ...
        robotat, MARKER_MOVIL, 'eulxyz');

    pose74 = robotat_get_pose( ...
        robotat, MARKER_OBJETIVO, 'eulxyz');

    objetivo_x = pose74(1);
    objetivo_y = pose74(2);

    fprintf( ...
        "Objetivo M74: X=%.3f, Y=%.3f m\n", ...
        objetivo_x, objetivo_y);

    %% CREAR FIGURA

    fig = figure( ...
        'Name', 'Robotat - Trayectoria 2D', ...
        'NumberTitle', 'off', ...
        'Color', 'w');

    ax = axes(fig);

    hold(ax, 'on');
    grid(ax, 'on');
    axis(ax, 'equal');

    xlabel(ax, 'X global (m)');
    ylabel(ax, 'Y global (m)');

    title(ax, 'Trayectoria M30 hacia M74');

    % Ampliar plano desde el inicio
    xlim(ax, X_LIM_INICIAL);
    ylim(ax, Y_LIM_INICIAL);

    %% OBJETIVO MOVIL M74

    hObjetivo = plot(ax, ...
        objetivo_x, objetivo_y, ...
        'rp', ...
        'MarkerSize', 16, ...
        'MarkerFaceColor', 'r', ...
        'DisplayName', 'Marker 74 - Objetivo');

    %% TRAYECTORIA M30

    hTrayectoria = plot(ax, ...
        NaN, NaN, ...
        'b-', ...
        'LineWidth', 2, ...
        'DisplayName', 'Trayectoria M30');

    %% POSICION ACTUAL M30

    hActual = plot(ax, ...
        NaN, NaN, ...
        'bo', ...
        'MarkerSize', 8, ...
        'MarkerFaceColor', 'b', ...
        'DisplayName', 'Posicion actual M30');

    %% ORIENTACION ACTUAL

    hFlecha = quiver(ax, ...
        NaN, NaN, NaN, NaN, ...
        0, ...
        'Color', [0 0.6 0], ...
        'LineWidth', 2.5, ...
        'MaxHeadSize', 1.5, ...
        'DisplayName', 'Orientacion M30');

    %% SILUETA ACTUAL

    hRobot = patch(ax, ...
        NaN, NaN, ...
        [0.1 0.4 0.9], ...
        'FaceAlpha', 0.75, ...
        'EdgeColor', [0 0.2 0.6], ...
        'HandleVisibility', 'off');

    %% HISTORIAL DE POSES

    ultima_pose_x = NaN;
    ultima_pose_y = NaN;

    legend(ax, 'Location', 'best');

    %% INICIAR ADQUISICION

    reloj = tic;

    disp("Capturando trayectoria...");
    disp("Marker 74 se actualiza en tiempo real.");
    disp("Cierra la grafica para finalizar.");

    while isgraphics(fig)

        inicio_ciclo = tic;

        %% LEER MARKER 30

        pose30 = robotat_get_pose( ...
            robotat, MARKER_MOVIL, 'eulxyz');

        x = pose30(1);
        y = pose30(2);
        yaw_deg = pose30(6);

        %% LEER MARKER 74 NUEVAMENTE

        pose74 = robotat_get_pose( ...
            robotat, MARKER_OBJETIVO, 'eulxyz');

        nuevo_objetivo_x = pose74(1);
        nuevo_objetivo_y = pose74(2);

        %% VALIDAR DATOS

        if any(~isfinite([x y yaw_deg ...
                          nuevo_objetivo_x ...
                          nuevo_objetivo_y]))

            pause(dt);
            continue;

        end

        %% ACTUALIZAR OBJETIVO

        objetivo_x = nuevo_objetivo_x;
        objetivo_y = nuevo_objetivo_y;

        set(hObjetivo, ...
            'XData', objetivo_x, ...
            'YData', objetivo_y);

        %% ORIENTACION M30

        theta_deg = yaw_deg + OFFSET_ORIENTACION_DEG;
        theta = deg2rad(theta_deg);

        dx = LONG_FLECHA * cos(theta);
        dy = LONG_FLECHA * sin(theta);

        %% GUARDAR DATOS

        trayectoria_x(end+1,1) = x;
        trayectoria_y(end+1,1) = y;
        orientaciones_deg(end+1,1) = theta_deg;
        tiempos(end+1,1) = toc(reloj);

        objetivo_hist_x(end+1,1) = objetivo_x;
        objetivo_hist_y(end+1,1) = objetivo_y;

        %% ACTUALIZAR TRAYECTORIA

        set(hTrayectoria, ...
            'XData', trayectoria_x, ...
            'YData', trayectoria_y);

        set(hActual, ...
            'XData', x, ...
            'YData', y);

        %% ACTUALIZAR FLECHA

        set(hFlecha, ...
            'XData', x, ...
            'YData', y, ...
            'UData', dx, ...
            'VData', dy);

        %% SILUETA RECTANGULAR

        local = [
            -LARGO_ROBOT/2, -ANCHO_ROBOT/2;
             LARGO_ROBOT/2, -ANCHO_ROBOT/2;
             LARGO_ROBOT/2,  ANCHO_ROBOT/2;
            -LARGO_ROBOT/2,  ANCHO_ROBOT/2
        ];

        R = [
            cos(theta), -sin(theta);
            sin(theta),  cos(theta)
        ];

        puntos = (R * local')';

        puntos(:,1) = puntos(:,1) + x;
        puntos(:,2) = puntos(:,2) + y;

        set(hRobot, ...
            'XData', puntos(:,1), ...
            'YData', puntos(:,2));

        %% HISTORIAL DE POSES

        nueva_pose = isnan(ultima_pose_x) || ...
            hypot(x - ultima_pose_x, ...
                  y - ultima_pose_y) >= DISTANCIA_POSE;

        if nueva_pose

            patch(ax, ...
                puntos(:,1), ...
                puntos(:,2), ...
                [0.3 0.6 1.0], ...
                'FaceAlpha', ALPHA_HISTORIAL, ...
                'EdgeColor', 'none', ...
                'HandleVisibility', 'off');

            quiver(ax, ...
                x, y, dx, dy, 0, ...
                'Color', [0.65 0.8 0.65], ...
                'LineWidth', 1, ...
                'HandleVisibility', 'off');

            ultima_pose_x = x;
            ultima_pose_y = y;

        end

        %% AMPLIAR EJES SI ES NECESARIO

        limites_x = xlim(ax);
        limites_y = ylim(ax);

        min_x = min([x, objetivo_x]);
        max_x = max([x, objetivo_x]);

        min_y = min([y, objetivo_y]);
        max_y = max([y, objetivo_y]);

        if min_x < limites_x(1) + MARGEN_EJES
            limites_x(1) = min_x - MARGEN_EJES;
        end

        if max_x > limites_x(2) - MARGEN_EJES
            limites_x(2) = max_x + MARGEN_EJES;
        end

        if min_y < limites_y(1) + MARGEN_EJES
            limites_y(1) = min_y - MARGEN_EJES;
        end

        if max_y > limites_y(2) - MARGEN_EJES
            limites_y(2) = max_y + MARGEN_EJES;
        end

        xlim(ax, limites_x);
        ylim(ax, limites_y);

        %% DISTANCIA AL OBJETIVO

        distancia = hypot( ...
            objetivo_x - x, ...
            objetivo_y - y);

        title(ax, sprintf( ...
            'M30 -> M74 | Distancia=%.3f m | Yaw=%.1f deg', ...
            distancia, theta_deg));

        drawnow limitrate;

        %% CONDICION DE LLEGADA

        if distancia <= TOLERANCIA

            disp("OBJETIVO M74 ALCANZADO");
            break;

        end

        %% CONTROL DE MUESTREO

        restante = dt - toc(inicio_ciclo);

        if restante > 0
            pause(restante);
        end

    end

catch ME

    warning("Error durante captura: %s", ...
        ME.message);

end

%% DESCONECTAR ROBOTAT

if ~isempty(robotat)
    robotat_disconnect(robotat);
end

disp("Robotat desconectado.");

%% GUARDAR RESULTADOS

if ~isempty(trayectoria_x)

    datos = table( ...
        tiempos, ...
        trayectoria_x, ...
        trayectoria_y, ...
        orientaciones_deg, ...
        objetivo_hist_x, ...
        objetivo_hist_y, ...
        'VariableNames', ...
        {'Tiempo_s', 'X_m', 'Y_m', 'Yaw_deg', ...
         'Objetivo_X_m', 'Objetivo_Y_m'});

    writetable(datos, ...
        'trayectoria_marker30_a_74.csv');

    save( ...
        'trayectoria_marker30_a_74.mat', ...
        'datos', ...
        'objetivo_x', ...
        'objetivo_y');

    fprintf("\n");
    fprintf("====================================\n");
    fprintf("POSE FINAL MARKER 30\n");
    fprintf("====================================\n");
    fprintf("X final = %.4f m\n", trayectoria_x(end));
    fprintf("Y final = %.4f m\n", trayectoria_y(end));
    fprintf("Yaw final = %.2f grados\n", ...
        orientaciones_deg(end));
    fprintf("====================================\n");

    disp("Datos guardados en CSV y MAT.");

else

    disp("No se registraron muestras validas.");

end
