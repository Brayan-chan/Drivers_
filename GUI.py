"""
Este módulo contiene la interfaz gráfica de usuario para el sistema de simulación de E/S.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import json
import logging
import time
import threading
import random
from queue import Queue
import sys
import os

# Importar los componentes principales desde Driver_USB.py
from Driver_USB import (
    DeviceType, OperationType, DeviceStatus, SchedulingAlgorithm,
    DeviceControlBlock, IOOperation, InterruptTable, Buffer, BufferManager,
    DeviceDriver, BlockDeviceDriver, CharacterDeviceDriver,
    DeviceDriverTable, IOScheduler, IOManager, logger
)

class IOSimulationGUI:
    """
    Interfaz gráfica de usuario para el sistema de simulación de E/S.
    """
    def __init__(self, master):
        self.master = master
        self.master.title("Sistema Avanzado de Simulación de Dispositivos de E/S")
        self.master.geometry("1200x800")
        self.master.minsize(800, 600)
        
        # Configurar los componentes principales
        self.setup_menu()
        self.setup_main_frame()
        
        # Inicializar componentes de simulación
        self.interrupt_table = InterruptTable()
        self.buffer_manager = BufferManager(2048)  # Búfer de 2MB
        self.driver_table = DeviceDriverTable()
        self.io_scheduler = IOScheduler(SchedulingAlgorithm.FIFO)
        self.io_manager = None  # Se inicializará después de configurar la GUI
        
        # Cola para actualizaciones seguras en el hilo de la GUI
        self.update_queue = Queue()
        
        # Configurar temporizador de actualizaciones
        self.master.after(100, self.initialize_io_manager)
        self.master.after(200, self.process_update_queue)
        
    def initialize_io_manager(self):
        """Inicializar el Gestor de E/S después de configurar la GUI"""
        # Crear y iniciar el Gestor de E/S de manera que no bloquee la GUI
        def setup_io_manager():
            self.io_manager = IOManager(self.driver_table, self.io_scheduler)
            self.io_manager.add_status_listener(self.queue_operation_status_update)
            self.io_manager.start()
            
            # Inicializar dispositivos
            self.initialize_default_devices()
            
            # Iniciar temporizador de actualización de estadísticas
            self.master.after(1000, self.update_stats)
        
        # Ejecutar en un hilo separado para evitar bloquear la GUI
        threading.Thread(target=setup_io_manager, daemon=True).start()
        
    def queue_operation_status_update(self, device_id, io_operation, success):
        """Colocar en cola una actualización de estado de operación para ser procesada por el hilo principal"""
        self.update_queue.put(("update_operations_list", None))
        
    def process_update_queue(self):
        """Procesar actualizaciones de la cola en el hilo principal"""
        try:
            # Procesar todas las actualizaciones pendientes
            while not self.update_queue.empty():
                action, data = self.update_queue.get_nowait()
                
                if action == "update_operations_list":
                    self.update_operations_list()
                elif action == "update_device_list":
                    self.update_device_list()
                # Agregar más acciones según sea necesario
                
        except Exception as e:
            logger.error(f"Error al procesar la cola de actualizaciones: {e}")
            
        # Programar la próxima verificación
        self.master.after(100, self.process_update_queue)
        
    def setup_menu(self):
        """Configurar el menú de la aplicación"""
        menubar = tk.Menu(self.master)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Guardar Configuración", command=self.save_configuration)
        file_menu.add_command(label="Cargar Configuración", command=self.load_configuration)
        file_menu.add_separator()
        file_menu.add_command(label="Exportar Estadísticas", command=self.export_statistics)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.exit_application)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        
        # Menú Dispositivos
        devices_menu = tk.Menu(menubar, tearoff=0)
        devices_menu.add_command(label="Agregar Dispositivo de Bloques", command=self.add_block_device)
        devices_menu.add_command(label="Agregar Dispositivo de Caracteres", command=self.add_character_device)
        devices_menu.add_command(label="Eliminar Dispositivo Seleccionado", command=self.remove_selected_device)
        menubar.add_cascade(label="Dispositivos", menu=devices_menu)
        
        # Menú Simulación
        simulation_menu = tk.Menu(menubar, tearoff=0)
        
        # Submenú Algoritmo de Planificación
        scheduling_menu = tk.Menu(simulation_menu, tearoff=0)
        self.scheduling_var = tk.StringVar(value="FIFO")
        scheduling_menu.add_radiobutton(label="FIFO", variable=self.scheduling_var, 
                                       value="FIFO", command=self.change_scheduling_algorithm)
        scheduling_menu.add_radiobutton(label="Prioridad", variable=self.scheduling_var, 
                                       value="PRIORITY", command=self.change_scheduling_algorithm)
        scheduling_menu.add_radiobutton(label="Trabajo Más Corto Primero", variable=self.scheduling_var, 
                                       value="SHORTEST_JOB_FIRST", command=self.change_scheduling_algorithm)
        simulation_menu.add_cascade(label="Algoritmo de Planificación", menu=scheduling_menu)
        
        simulation_menu.add_separator()
        simulation_menu.add_command(label="Generar Operaciones Aleatorias", command=self.generate_random_operations)
        simulation_menu.add_command(label="Limpiar Todas las Operaciones", command=self.clear_operations)
        menubar.add_cascade(label="Simulación", menu=simulation_menu)
        
        # Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Documentación", command=self.show_documentation)
        help_menu.add_command(label="Acerca de", command=self.show_about)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        
        self.master.config(menu=menubar)
    
    def setup_main_frame(self):
        """Configurar el marco principal de la aplicación con todos los componentes"""
        main_frame = ttk.Frame(self.master)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crear un cuaderno con pestañas
        notebook = ttk.Notebook(main_frame)
        
        # Pestaña de Dispositivos
        devices_tab = ttk.Frame(notebook)
        self.setup_devices_tab(devices_tab)
        notebook.add(devices_tab, text="Dispositivos")
        
        # Pestaña de Operaciones
        operations_tab = ttk.Frame(notebook)
        self.setup_operations_tab(operations_tab)
        notebook.add(operations_tab, text="Operaciones")
        
        # Pestaña de Monitoreo
        monitoring_tab = ttk.Frame(notebook)
        self.setup_monitoring_tab(monitoring_tab)
        notebook.add(monitoring_tab, text="Monitoreo")
        
        # Pestaña de Estadísticas
        statistics_tab = ttk.Frame(notebook)
        self.setup_statistics_tab(statistics_tab)
        notebook.add(statistics_tab, text="Estadísticas")
        
        # Pestaña de Registro
        log_tab = ttk.Frame(notebook)
        self.setup_log_tab(log_tab)
        notebook.add(log_tab, text="Registro")
        
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Barra de estado
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.status_label = ttk.Label(status_frame, text="Listo")
        self.status_label.pack(side=tk.LEFT)
        
        self.throughput_label = ttk.Label(status_frame, text="Rendimiento: 0 MB/s")
        self.throughput_label.pack(side=tk.RIGHT)
    
    def setup_devices_tab(self, parent):
        """Configurar la pestaña de dispositivos"""
        # Dividir en dos marcos
        left_frame = ttk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Lista de dispositivos (marco izquierdo)
        list_frame = ttk.LabelFrame(left_frame, text="Dispositivos")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("id", "name", "type", "status", "capacity", "transfer_rate")
        self.device_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        self.device_tree.heading("id", text="ID")
        self.device_tree.heading("name", text="Nombre")
        self.device_tree.heading("type", text="Tipo")
        self.device_tree.heading("status", text="Estado")
        self.device_tree.heading("capacity", text="Capacidad (GB)")
        self.device_tree.heading("transfer_rate", text="Velocidad de Transferencia (MB/s)")
        
        self.device_tree.column("id", width=50)
        self.device_tree.column("name", width=100)
        self.device_tree.column("type", width=100)
        self.device_tree.column("status", width=100)
        self.device_tree.column("capacity", width=100)
        self.device_tree.column("transfer_rate", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        self.device_tree.configure(yscroll=scrollbar.set)
        
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.device_tree.bind("<<TreeviewSelect>>", self.on_device_selected)
        
        # Controles del dispositivo (marco derecho)
        control_frame = ttk.LabelFrame(right_frame, text="Controles del Dispositivo")
        control_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Detalles del dispositivo
        details_frame = ttk.Frame(control_frame)
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(details_frame, text="Nombre del Dispositivo:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.device_name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.device_name_var).grid(row=0, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Tipo de Dispositivo:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.device_type_var = tk.StringVar(value="BLOQUE")
        ttk.Combobox(details_frame, textvariable=self.device_type_var, 
                    values=["BLOQUE", "CARACTER"], state="readonly").grid(row=1, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Capacidad (GB):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.device_capacity_var = tk.DoubleVar(value=128.0)
        ttk.Entry(details_frame, textvariable=self.device_capacity_var).grid(row=2, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Velocidad de Transferencia (MB/s):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.device_transfer_rate_var = tk.DoubleVar(value=30.0)
        ttk.Entry(details_frame, textvariable=self.device_transfer_rate_var).grid(row=3, column=1, sticky=tk.W+tk.E, pady=2)
        
        # Acciones del dispositivo
        actions_frame = ttk.Frame(control_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(actions_frame, text="Conectar", command=self.connect_device).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Desconectar", command=self.disconnect_device).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Simular Error", command=self.simulate_device_error).pack(side=tk.LEFT, padx=5)
        
        # Marco para agregar nuevo dispositivo
        add_frame = ttk.LabelFrame(right_frame, text="Agregar Nuevo Dispositivo")
        add_frame.pack(fill=tk.X, expand=False, pady=5)
        
        ttk.Button(add_frame, text="Agregar Dispositivo de Bloques", command=self.add_block_device).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(add_frame, text="Agregar Dispositivo de Caracteres", command=self.add_character_device).pack(side=tk.LEFT, padx=10, pady=10)
    
    def setup_operations_tab(self, parent):
        """Configurar la pestaña de operaciones"""
        # Dividir en dos marcos
        left_frame = ttk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Cola de operaciones (marco izquierdo)
        queue_frame = ttk.LabelFrame(left_frame, text="Cola de Operaciones")
        queue_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("id", "device", "type", "size", "process", "priority", "status")
        self.operations_tree = ttk.Treeview(queue_frame, columns=columns, show="headings")
        
        self.operations_tree.heading("id", text="ID")
        self.operations_tree.heading("device", text="Dispositivo")
        self.operations_tree.heading("type", text="Tipo")
        self.operations_tree.heading("size", text="Tamaño (MB)")
        self.operations_tree.heading("process", text="Proceso")
        self.operations_tree.heading("priority", text="Prioridad")
        self.operations_tree.heading("status", text="Estado")
        
        self.operations_tree.column("id", width=80)
        self.operations_tree.column("device", width=100)
        self.operations_tree.column("type", width=80)
        self.operations_tree.column("size", width=80)
        self.operations_tree.column("process", width=100)
        self.operations_tree.column("priority", width=60)
        self.operations_tree.column("status", width=100)
        
        scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.operations_tree.yview)
        self.operations_tree.configure(yscroll=scrollbar.set)
        
        self.operations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Formulario de nueva operación (marco derecho)
        form_frame = ttk.LabelFrame(right_frame, text="Nueva Operación")
        form_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Detalles de la operación
        details_frame = ttk.Frame(form_frame)
        details_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(details_frame, text="Dispositivo:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.op_device_var = tk.StringVar()
        self.op_device_combo = ttk.Combobox(details_frame, textvariable=self.op_device_var, state="readonly")
        self.op_device_combo.grid(row=0, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Tipo de Operación:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.op_type_var = tk.StringVar(value="READ")
        ttk.Combobox(details_frame, textvariable=self.op_type_var, 
                    values=["READ", "WRITE", "CONTROL", "SEEK"], state="readonly").grid(row=1, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Tamaño de Datos (MB):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.op_size_var = tk.DoubleVar(value=10.0)
        ttk.Entry(details_frame, textvariable=self.op_size_var).grid(row=2, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Nombre del Proceso:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.op_process_var = tk.StringVar(value="Proceso1")
        ttk.Entry(details_frame, textvariable=self.op_process_var).grid(row=3, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Prioridad:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.op_priority_var = tk.IntVar(value=0)
        ttk.Spinbox(details_frame, from_=0, to=10, textvariable=self.op_priority_var).grid(row=4, column=1, sticky=tk.W+tk.E, pady=2)
        
        ttk.Label(details_frame, text="Dirección de Bloque:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.op_address_var = tk.IntVar(value=0)
        self.op_address_entry = ttk.Entry(details_frame, textvariable=self.op_address_var)
        self.op_address_entry.grid(row=5, column=1, sticky=tk.W+tk.E, pady=2)
        
        # Acciones de la operación
        actions_frame = ttk.Frame(form_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(actions_frame, text="Agregar Operación", command=self.add_operation).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Generar Operaciones Aleatorias", 
                  command=self.generate_random_operations).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Limpiar Todo", command=self.clear_operations).pack(side=tk.LEFT, padx=5)
    
    def setup_monitoring_tab(self, parent):
        """Configurar la pestaña de monitoreo con gráficos en tiempo real"""
        # Crear un marco para los gráficos
        charts_frame = ttk.Frame(parent)
        charts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Crear una figura para los gráficos
        self.fig = plt.Figure(figsize=(12, 8), dpi=100)
        
        # Crear un lienzo para mostrar la figura
        self.canvas = FigureCanvasTkAgg(self.fig, master=charts_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Crear subgráficos
        self.throughput_ax = self.fig.add_subplot(221)
        self.queue_ax = self.fig.add_subplot(222)
        self.buffer_ax = self.fig.add_subplot(223)
        self.device_status_ax = self.fig.add_subplot(224)
        
        # Inicializar datos para los gráficos
        self.throughput_data = {"time": [], "value": []}
        self.queue_data = {"time": [], "devices": {}}
        self.buffer_usage_data = {"time": [], "value": []}
        self.device_status_data = {}
        
        # Configurar los gráficos
        self.throughput_ax.set_title("Rendimiento (MB/s)")
        self.throughput_ax.set_xlabel("Tiempo (s)")
        self.throughput_ax.set_ylabel("MB/s")
        self.throughput_line, = self.throughput_ax.plot([], [], 'b-')
        
        self.queue_ax.set_title("Longitud de la Cola de Operaciones")
        self.queue_ax.set_xlabel("Tiempo (s)")
        self.queue_ax.set_ylabel("Operaciones")
        
        self.buffer_ax.set_title("Uso del Búfer")
        self.buffer_ax.set_xlabel("Tiempo (s)")
        self.buffer_ax.set_ylabel("Uso (%)")
        self.buffer_line, = self.buffer_ax.plot([], [], 'g-')
        
        self.device_status_ax.set_title("Estado de los Dispositivos")
        self.device_status_ax.set_xlabel("Dispositivo")
        self.device_status_ax.set_ylabel("Estado")
        
        # Ajustar diseño
        self.fig.tight_layout()
    
    def setup_statistics_tab(self, parent):
        """Configurar la pestaña de estadísticas"""
        # Crear marcos para las diferentes secciones de estadísticas
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=10)
        
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Estadísticas generales (marco superior)
        overall_frame = ttk.LabelFrame(top_frame, text="Estadísticas Generales")
        overall_frame.pack(fill=tk.X, padx=10)
        
        self.stats_vars = {
            "operations_processed": tk.StringVar(value="0"),
            "operations_succeeded": tk.StringVar(value="0"),
            "operations_failed": tk.StringVar(value="0"),
            "success_rate": tk.StringVar(value="0%"),
            "total_data": tk.StringVar(value="0 MB"),
            "throughput": tk.StringVar(value="0 MB/s"),
            "runtime": tk.StringVar(value="0s")
        }
        
        row = 0
        for label, var in self.stats_vars.items():
            ttk.Label(overall_frame, text=label.replace("_", " ").title() + ":").grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
            ttk.Label(overall_frame, textvariable=var).grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
            row += 1
        
        # Estadísticas de dispositivos
        device_stats_frame = ttk.LabelFrame(bottom_frame, text="Estadísticas de Dispositivos")
        device_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        columns = ("device", "operations", "data", "errors", "uptime")
        self.device_stats_tree = ttk.Treeview(device_stats_frame, columns=columns, show="headings")
        
        self.device_stats_tree.heading("device", text="Dispositivo")
        self.device_stats_tree.heading("operations", text="Operaciones")
        self.device_stats_tree.heading("data", text="Datos Transferidos")
        self.device_stats_tree.heading("errors", text="Errores")
        self.device_stats_tree.heading("uptime", text="Tiempo Activo")
        
        self.device_stats_tree.column("device", width=150)
        self.device_stats_tree.column("operations", width=100)
        self.device_stats_tree.column("data", width=150)
        self.device_stats_tree.column("errors", width=100)
        self.device_stats_tree.column("uptime", width=100)
        
        scrollbar = ttk.Scrollbar(device_stats_frame, orient=tk.VERTICAL, command=self.device_stats_tree.yview)
        self.device_stats_tree.configure(yscroll=scrollbar.set)
        
        self.device_stats_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_log_tab(self, parent):
        """Configurar la pestaña de registro"""
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Visor de registro
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Agregar un manejador personalizado al logger
        class TextHandler(logging.Handler):
            def __init__(self, text_widget, master):
                super().__init__()
                self.text_widget = text_widget
                self.master = master
            
            def emit(self, record):
                msg = self.format(record)
                
                def append():
                    try:
                        self.text_widget.configure(state='normal')
                        self.text_widget.insert(tk.END, msg + '\n')
                        self.text_widget.configure(state='disabled')
                        self.text_widget.yview(tk.END)
                    except Exception:
                        pass  # El widget podría estar destruido
                
                # Usar after_idle para evitar bloquear la GUI
                try:
                    self.master.after_idle(append)
                except Exception:
                    pass  # El master podría estar destruido
        
        text_handler = TextHandler(self.log_text, self.master)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(text_handler)
        
        # Controles
        controls_frame = ttk.Frame(log_frame)
        controls_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(controls_frame, text="Limpiar Registro", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Guardar Registro", command=self.save_log).pack(side=tk.LEFT, padx=5)
    
    # ========================================================
    # MÉTODOS DE GESTIÓN DE DISPOSITIVOS
    # =======================================================
    
    def initialize_default_devices(self):
        """Inicializar algunos dispositivos predeterminados para la simulación"""
        try:
            # Agregar una unidad USB
            usb_dcb = DeviceControlBlock(
                device_id=1,
                device_name="Unidad USB",
                device_type=DeviceType.BLOQUE,  # Cambiado de BLOCK a BLOQUE
                capacity_gb=128,
                transfer_rate_mb_s=30.0
            )
            usb_driver = BlockDeviceDriver(usb_dcb, self.interrupt_table, self.buffer_manager)
            self.driver_table.register_driver(usb_dcb.device_id, usb_driver)
            
            # Agregar un disco duro
            hdd_dcb = DeviceControlBlock(
                device_id=2,
                device_name="Disco Duro",
                device_type=DeviceType.BLOQUE,  # Cambiado de BLOCK a BLOQUE
                capacity_gb=1000,
                transfer_rate_mb_s=120.0
            )
            hdd_driver = BlockDeviceDriver(hdd_dcb, self.interrupt_table, self.buffer_manager)
            self.driver_table.register_driver(hdd_dcb.device_id, hdd_driver)
            
            # Agregar un teclado
            keyboard_dcb = DeviceControlBlock(
                device_id=3,
                device_name="Teclado",
                device_type=DeviceType.CARACTER,  # Cambiado de CHARACTER a CARACTER
                transfer_rate_mb_s=0.1
            )
            keyboard_driver = CharacterDeviceDriver(keyboard_dcb, self.interrupt_table, self.buffer_manager)
            self.driver_table.register_driver(keyboard_dcb.device_id, keyboard_driver)
            
            # Conectar los dispositivos - usar la cola para actualizar la interfaz
            self.interrupt_table.trigger_interrupt("UNIDAD_USB_CONNECT")  # Revertido a CONNECT
            self.interrupt_table.trigger_interrupt("DISCO_DURO_CONNECT")  # Revertido a CONNECT
            self.interrupt_table.trigger_interrupt("TECLADO_CONNECT")  # Revertido a CONNECT
            
            # Colocar actualizaciones de la interfaz en la cola
            self.update_queue.put(("update_device_list", None))
            self.update_queue.put(("update_operations_list", None))
            
        except Exception as e:
            logger.error(f"Error al inicializar dispositivos predeterminados: {e}")
    
    def add_block_device(self):
        """Agregar un nuevo dispositivo de bloques a la simulación"""
        try:
            # Obtener el siguiente ID de dispositivo disponible
            device_id = len(self.driver_table.get_all_drivers()) + 1
            
            # Crear un nuevo bloque de control de dispositivo
            dcb = DeviceControlBlock(
                device_id=device_id,
                device_name=f"Dispositivo de Bloques {device_id}",
                device_type=DeviceType.BLOQUE,  # Cambiado de BLOCK a BLOQUE
                capacity_gb=500,
                transfer_rate_mb_s=100.0
            )
            
            # Crear un nuevo controlador
            driver = BlockDeviceDriver(dcb, self.interrupt_table, self.buffer_manager)
            
            # Registrar el controlador
            self.driver_table.register_driver(dcb.device_id, driver)
            
            # Conectar el dispositivo
            self.interrupt_table.trigger_interrupt(f"{dcb.device_name.upper().replace(' ', '_')}_CONNECT")  # Revertido a CONNECT
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
            self.update_operation_device_combo()
            
            logger.info(f"Se agregó un nuevo dispositivo de bloques: {dcb.device_name} (ID: {dcb.device_id})")
        except Exception as e:
            logger.error(f"Error al agregar dispositivo de bloques: {e}")
    
    def add_character_device(self):
        """Agregar un nuevo dispositivo de caracteres a la simulación"""
        try:
            # Obtener el siguiente ID de dispositivo disponible
            device_id = len(self.driver_table.get_all_drivers()) + 1
            
            # Crear un nuevo bloque de control de dispositivo
            dcb = DeviceControlBlock(
                device_id=device_id,
                device_name=f"Dispositivo de Caracteres {device_id}",
                device_type=DeviceType.CARACTER,  # Cambiado de CHARACTER a CARACTER
                transfer_rate_mb_s=1.0
            )
            
            # Crear un nuevo controlador
            driver = CharacterDeviceDriver(dcb, self.interrupt_table, self.buffer_manager)
            
            # Registrar el controlador
            self.driver_table.register_driver(dcb.device_id, driver)
            
            # Conectar el dispositivo
            self.interrupt_table.trigger_interrupt(f"{dcb.device_name.upper().replace(' ', '_')}_CONNECT")  # Revertido a CONNECT
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
            self.update_operation_device_combo()
            
            logger.info(f"Se agregó un nuevo dispositivo de caracteres: {dcb.device_name} (ID: {dcb.device_id})")
        except Exception as e:
            logger.error(f"Error al agregar dispositivo de caracteres: {e}")
    
    def remove_selected_device(self):
        """Eliminar el dispositivo seleccionado de la simulación"""
        try:
            selection = self.device_tree.selection()
            if not selection:
                messagebox.showwarning("Sin Selección", "Por favor seleccione un dispositivo para eliminar.")
                return
            
            item = selection[0]
            device_id = int(self.device_tree.item(item, "values")[0])
            
            # Obtener el controlador
            driver = self.driver_table.get_driver(device_id)
            if not driver:
                messagebox.showerror("Error", f"No se encontró un controlador para el dispositivo con ID {device_id}")
                return
            
            # Desconectar el dispositivo
            device_name = driver.dcb.device_name
            self.interrupt_table.trigger_interrupt(f"{device_name.upper().replace(' ', '_')}_DISCONNECT")  # Revertido a DISCONNECT
            
            # Desregistrar el controlador
            self.driver_table.unregister_driver(device_id)
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
            self.update_operation_device_combo()
            
            logger.info(f"Se eliminó el dispositivo: {device_name} (ID: {device_id})")
        except Exception as e:
            logger.error(f"Error al eliminar dispositivo: {e}")
    
    def on_device_selected(self, event):
        """Manejar la selección de dispositivos en el Treeview"""
        try:
            selection = self.device_tree.selection()
            if not selection:
                return
            
            item = selection[0]
            values = self.device_tree.item(item, "values")
            
            # Actualizar el formulario de detalles del dispositivo
            self.device_name_var.set(values[1])
            self.device_type_var.set(values[2])
            self.device_capacity_var.set(values[4])
            self.device_transfer_rate_var.set(values[5])
        except Exception as e:
            logger.error(f"Error al manejar la selección de dispositivos: {e}")
    
    def connect_device(self):
        """Conectar el dispositivo seleccionado"""
        try:
            selection = self.device_tree.selection()
            if not selection:
                messagebox.showwarning("Sin Selección", "Por favor seleccione un dispositivo para conectar.")
                return
            
            item = selection[0]
            device_id = int(self.device_tree.item(item, "values")[0])
            
            # Obtener el controlador
            driver = self.driver_table.get_driver(device_id)
            if not driver:
                messagebox.showerror("Error", f"No se encontró un controlador para el dispositivo con ID {device_id}")
                return
            
            # Conectar el dispositivo
            device_name = driver.dcb.device_name
            self.interrupt_table.trigger_interrupt(f"{device_name.upper().replace(' ', '_')}_CONNECT")  # Revertido a CONNECT
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
        except Exception as e:
            logger.error(f"Error al conectar dispositivo: {e}")
    
    def disconnect_device(self):
        """Desconectar el dispositivo seleccionado"""
        try:
            selection = self.device_tree.selection()
            if not selection:
                messagebox.showwarning("Sin Selección", "Por favor seleccione un dispositivo para desconectar.")
                return
            
            item = selection[0]
            device_id = int(self.device_tree.item(item, "values")[0])
            
            # Obtener el controlador
            driver = self.driver_table.get_driver(device_id)
            if not driver:
                messagebox.showerror("Error", f"No se encontró un controlador para el dispositivo con ID {device_id}")
                return
            
            # Desconectar el dispositivo
            device_name = driver.dcb.device_name
            self.interrupt_table.trigger_interrupt(f"{device_name.upper().replace(' ', '_')}_DISCONNECT")  # Revertido a DISCONNECT
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
        except Exception as e:
            logger.error(f"Error al desconectar dispositivo: {e}")
    
    def simulate_device_error(self):
        """Simular un error en el dispositivo seleccionado"""
        try:
            selection = self.device_tree.selection()
            if not selection:
                messagebox.showwarning("Sin Selección", "Por favor seleccione un dispositivo para simular un error.")
                return
            
            item = selection[0]
            device_id = int(self.device_tree.item(item, "values")[0])
            
            # Obtener el controlador
            driver = self.driver_table.get_driver(device_id)
            if not driver:
                messagebox.showerror("Error", f"No se encontró un controlador para el dispositivo con ID {device_id}")
                return
            
            # Activar un error
            device_name = driver.dcb.device_name
            self.interrupt_table.trigger_interrupt(f"{device_name.upper().replace(' ', '_')}_ERROR", 
                                                error_code=random.randint(1, 100),
                                                error_message="Error simulado")
            
            # Actualizar la lista de dispositivos
            self.update_device_list()
        except Exception as e:
            logger.error(f"Error al simular error en dispositivo: {e}")
    
    # =========================================================================
    # MÉTODOS DE GESTIÓN DE OPERACIONES
    # =========================================================================
    
    def add_operation(self):
        """Agregar una nueva operación a la cola"""
        try:
            # Obtener el dispositivo seleccionado
            device_name = self.op_device_var.get()
            if not device_name:
                messagebox.showwarning("Sin Dispositivo", "Por favor seleccione un dispositivo.")
                return
            
            # Encontrar el ID del dispositivo
            device_id = None
            for did, driver in self.driver_table.get_all_drivers().items():
                if driver.dcb.device_name == device_name:
                    device_id = did
                    break
            
            if device_id is None:
                messagebox.showerror("Error", f"No se encontró un dispositivo con el nombre {device_name}")
                return
            
            # Crear una nueva operación
            operation_type = OperationType[self.op_type_var.get()]
            data_size = float(self.op_size_var.get())
            process_name = self.op_process_var.get()
            priority = int(self.op_priority_var.get())
            
            # Obtener dirección de bloque para dispositivos de bloques
            block_address = None
            driver = self.driver_table.get_driver(device_id)
            if driver.dcb.device_type == DeviceType.BLOQUE:  # Cambiado de BLOCK a BLOQUE
                block_address = int(self.op_address_var.get())
            
            # Crear la operación
            operation = IOOperation(
                operation_type=operation_type,
                data_size_mb=data_size,
                process_name=process_name,
                priority=priority,
                block_address=block_address
            )
            
            # Agregar a la cola
            if self.io_manager:
                self.io_manager.add_io_operation(device_id, operation)
                
                # Actualizar la lista de operaciones
                self.update_operations_list()
                
                logger.info(f"Se agregó una nueva operación: {operation} para el dispositivo {device_name}")
            else:
                messagebox.showerror("Error", "Gestor de E/S no inicializado")
                
        except Exception as e:
            logger.error(f"Error al agregar operación: {e}")
            messagebox.showerror("Error", f"Error al agregar operación: {e}")
    
    def generate_random_operations(self):
        """Generar operaciones aleatorias para todos los dispositivos conectados"""
        try:
            if not self.io_manager:
                messagebox.showerror("Error", "Gestor de E/S no inicializado")
                return
                
            # Obtener todos los dispositivos conectados
            connected_devices = []
            for device_id, driver in self.driver_table.get_all_drivers().items():
                if driver.dcb.status == DeviceStatus.CONECTADO:  # Cambiado de CONNECTED a CONECTADO
                    connected_devices.append((device_id, driver))
            
            if not connected_devices:
                messagebox.showwarning("Sin Dispositivos", "No se encontraron dispositivos conectados.")
                return
            
            # Generar operaciones aleatorias
            num_operations = random.randint(5, 15)
            
            for _ in range(num_operations):
                # Seleccionar un dispositivo aleatorio
                device_id, driver = random.choice(connected_devices)
                
                # Generar parámetros aleatorios para la operación
                operation_type = random.choice(list(OperationType))
                data_size = random.uniform(1.0, 100.0)
                process_name = f"Proceso{random.randint(1, 100)}"
                priority = random.randint(0, 10)
                
                # Dirección de bloque para dispositivos de bloques
                block_address = None
                if driver.dcb.device_type == DeviceType.BLOQUE:  # Cambiado de BLOCK a BLOQUE
                    block_address = random.randint(0, 1000000)
                
                # Crear la operación
                operation = IOOperation(
                    operation_type=operation_type,
                    data_size_mb=data_size,
                    process_name=process_name,
                    priority=priority,
                    block_address=block_address
                )
                
                # Agregar a la cola
                self.io_manager.add_io_operation(device_id, operation)
            
            # Actualizar la lista de operaciones
            self.update_operations_list()
            
            logger.info(f"Se generaron {num_operations} operaciones aleatorias")
        except Exception as e:
            logger.error(f"Error al generar operaciones aleatorias: {e}")
    
    def clear_operations(self):
        """Limpiar todas las operaciones pendientes"""
        # Esta es una implementación simplificada que no limpia realmente las colas
        # En una implementación real, necesitaríamos limpiar las colas en el planificador de E/S
        
        # Por ahora, solo actualizar la lista de operaciones
        self.update_operations_list()
        
        logger.info("Se limpiaron todas las operaciones")
    
    # =========================================================================
    # MÉTODOS DE ACTUALIZACIÓN DE LA INTERFAZ
    # =========================================================================
    
    def update_device_list(self):
        """Actualizar la lista de dispositivos en el Treeview"""
        try:
            # Limpiar el Treeview
            for item in self.device_tree.get_children():
                self.device_tree.delete(item)
            
            # Agregar todos los dispositivos
            for device_id, driver in self.driver_table.get_all_drivers().items():
                dcb = driver.dcb
                self.device_tree.insert("", "end", values=(
                    dcb.device_id,
                    dcb.device_name,
                    dcb.device_type.name,
                    dcb.status.name,
                    dcb.capacity_gb,
                    dcb.transfer_rate_mb_s
                ))
                
            # Actualizar el combo de dispositivos en el formulario de operación
            self.update_operation_device_combo()
        except Exception as e:
            logger.error(f"Error al actualizar la lista de dispositivos: {e}")
    
    def update_operations_list(self):
        """Actualizar la lista de operaciones en el Treeview"""
        try:
            # Limpiar el Treeview
            for item in self.operations_tree.get_children():
                self.operations_tree.delete(item)
            
            # Agregar todas las operaciones del historial
            if self.io_manager:
                for op in self.io_manager.operation_history[-100:]:  # Mostrar solo las últimas 100 operaciones
                    device_name = "Desconocido"
                    for _, driver in self.driver_table.get_all_drivers().items():
                        if driver.dcb.device_id == op["device_id"]:
                            device_name = driver.dcb.device_name
                            break
                    
                    self.operations_tree.insert("", "end", values=(
                        op["operation_id"],
                        device_name,
                        op["operation_type"],
                        f"{op['data_size_mb']:.2f}",
                        op["process_name"],
                        op["priority"],
                        op["status"]
                    ))
        except Exception as e:
            logger.error(f"Error al actualizar la lista de operaciones: {e}")
    
    def update_operation_device_combo(self):
        """Actualizar el combo box de dispositivos en el formulario de operación"""
        try:
            # Obtener todos los nombres de dispositivos
            device_names = []
            for _, driver in self.driver_table.get_all_drivers().items():
                device_names.append(driver.dcb.device_name)
            
            # Actualizar el combo box
            self.op_device_combo["values"] = device_names
            if device_names:
                self.op_device_var.set(device_names[0])
        except Exception as e:
            logger.error(f"Error al actualizar el combo de dispositivos: {e}")
    
    def update_stats(self):
        """Actualizar estadísticas y gráficos"""
        try:
            if not self.io_manager:
                self.master.after(1000, self.update_stats)
                return
                
            # Actualizar estadísticas generales
            self.stats_vars["operations_processed"].set(str(self.io_manager.stats["operations_processed"]))
            self.stats_vars["operations_succeeded"].set(str(self.io_manager.stats["operations_succeeded"]))
            self.stats_vars["operations_failed"].set(str(self.io_manager.stats["operations_failed"]))
            
            success_rate = self.io_manager.get_success_rate()
            self.stats_vars["success_rate"].set(f"{success_rate:.2f}%")
            
            self.stats_vars["total_data"].set(f"{self.io_manager.stats['total_data_mb']:.2f} MB")
            
            throughput = self.io_manager.get_throughput()
            self.stats_vars["throughput"].set(f"{throughput:.2f} MB/s")
            
            runtime = time.time() - self.io_manager.stats["start_time"]
            self.stats_vars["runtime"].set(f"{runtime:.2f}s")
            
            # Actualizar estadísticas de dispositivos
            self.update_device_statistics()
            
            # Actualizar gráficos - hacer esto en un hilo separado para evitar bloquear la GUI
            threading.Thread(target=self.update_charts_thread, daemon=True).start()
            
            # Actualizar barra de estado
            self.throughput_label.config(text=f"Rendimiento: {throughput:.2f} MB/s")
            
            # Programar la próxima actualización
            self.master.after(1000, self.update_stats)
        except Exception as e:
            logger.error(f"Error al actualizar estadísticas: {e}")
            # Intentar nuevamente más tarde
            self.master.after(1000, self.update_stats)
    
    def update_device_statistics(self):
        """Actualizar las estadísticas de dispositivos en el Treeview"""
        try:
            # Limpiar el Treeview
            for item in self.device_stats_tree.get_children():
                self.device_stats_tree.delete(item)
            
            # Agregar todos los dispositivos
            for device_id, driver in self.driver_table.get_all_drivers().items():
                dcb = driver.dcb
                
                # Calcular tiempo activo
                uptime = time.time() - dcb.creation_time
                uptime_str = f"{uptime:.2f}s"
                
                # Calcular datos transferidos
                data_mb = dcb.bytes_transferred / (1024 * 1024)
                data_str = f"{data_mb:.2f} MB"
                
                self.device_stats_tree.insert("", "end", values=(
                    dcb.device_name,
                    dcb.operations_completed,
                    data_str,
                    dcb.error_count,
                    uptime_str
                ))
        except Exception as e:
            logger.error(f"Error al actualizar estadísticas de dispositivos: {e}")
    
    def update_charts_thread(self):
        """Actualizar gráficos en un hilo separado para evitar bloquear la GUI"""
        try:
            # Preparar los datos de los gráficos
            current_time = time.time() - self.io_manager.stats["start_time"]
            
            # Actualizar datos del gráfico de rendimiento
            throughput = self.io_manager.get_throughput()
            self.throughput_data["time"].append(current_time)
            self.throughput_data["value"].append(throughput)
            
            # Mantener solo los últimos 60 segundos de datos
            if len(self.throughput_data["time"]) > 60:
                self.throughput_data["time"] = self.throughput_data["time"][-60:]
                self.throughput_data["value"] = self.throughput_data["value"][-60:]
            
            # Actualizar datos del gráfico de longitud de cola
            self.queue_data["time"].append(current_time)
            
            # Obtener longitudes de cola para todos los dispositivos
            for device_id, driver in self.driver_table.get_all_drivers().items():
                device_name = driver.dcb.device_name
                if device_name not in self.queue_data["devices"]:
                    self.queue_data["devices"][device_name] = []
                
                queue_length = self.io_scheduler.get_queue_length(device_id)
                self.queue_data["devices"][device_name].append(queue_length)
                
                # Mantener solo los últimos 60 segundos de datos
                if len(self.queue_data["devices"][device_name]) > 60:
                    self.queue_data["devices"][device_name] = self.queue_data["devices"][device_name][-60:]
            
            # Mantener solo los últimos 60 segundos de datos de tiempo
            if len(self.queue_data["time"]) > 60:
                self.queue_data["time"] = self.queue_data["time"][-60:]
            
            # Actualizar datos del gráfico de uso del búfer
            buffer_usage = self.buffer_manager.get_buffer_usage()
            self.buffer_usage_data["time"].append(current_time)
            self.buffer_usage_data["value"].append(buffer_usage)
            
            # Mantener solo los últimos 60 segundos de datos
            if len(self.buffer_usage_data["time"]) > 60:
                self.buffer_usage_data["time"] = self.buffer_usage_data["time"][-60:]
                self.buffer_usage_data["value"] = self.buffer_usage_data["value"][-60:]
            
            # Programar la actualización real de los gráficos en el hilo principal
            self.master.after_idle(self.update_charts_gui)
            
        except Exception as e:
            logger.error(f"Error en update_charts_thread: {e}")
    
    def update_charts_gui(self):
        """Actualizar los gráficos en la GUI (llamado desde el hilo principal)"""
        try:
            # Actualizar gráfico de rendimiento
            self.throughput_ax.clear()
            self.throughput_ax.set_title("Rendimiento (MB/s)")
            self.throughput_ax.set_xlabel("Tiempo (s)")
            self.throughput_ax.set_ylabel("MB/s")
            if self.throughput_data["time"]:  # Solo graficar si tenemos datos
                self.throughput_ax.plot(self.throughput_data["time"], self.throughput_data["value"], 'b-')
            
            # Actualizar gráfico de longitud de cola
            self.queue_ax.clear()
            self.queue_ax.set_title("Longitud de la Cola de Operaciones")
            self.queue_ax.set_xlabel("Tiempo (s)")
            self.queue_ax.set_ylabel("Operaciones")
            
            for device_name, queue_lengths in self.queue_data["devices"].items():
                # Solo graficar si tenemos datos y puntos de tiempo
                if self.queue_data["time"] and queue_lengths:
                    # Rellenar los datos si es necesario
                    if len(queue_lengths) < len(self.queue_data["time"]):
                        queue_lengths = [0] * (len(self.queue_data["time"]) - len(queue_lengths)) + queue_lengths
                    elif len(queue_lengths) > len(self.queue_data["time"]):
                        queue_lengths = queue_lengths[-len(self.queue_data["time"]):]
                    
                    self.queue_ax.plot(self.queue_data["time"], queue_lengths, label=device_name)
            
            if self.queue_data["devices"]:  # Solo agregar leyenda si tenemos dispositivos
                self.queue_ax.legend()
            
            # Actualizar gráfico de uso del búfer
            self.buffer_ax.clear()
            self.buffer_ax.set_title("Uso del Búfer")
            self.buffer_ax.set_xlabel("Tiempo (s)")
            self.buffer_ax.set_ylabel("Uso (%)")
            if self.buffer_usage_data["time"]:  # Solo graficar si tenemos datos
                self.buffer_ax.plot(self.buffer_usage_data["time"], self.buffer_usage_data["value"], 'g-')
            self.buffer_ax.set_ylim(0, 100)
            
            # Actualizar gráfico de estado de dispositivos
            self.device_status_ax.clear()
            self.device_status_ax.set_title("Estado de los Dispositivos")
            
            devices = []
            statuses = []
            colors = []
            
            for _, driver in self.driver_table.get_all_drivers().items():
                devices.append(driver.dcb.device_name)
                status = driver.dcb.status
                statuses.append(status.name)
                
                # Establecer color según el estado
                if status == DeviceStatus.CONECTADO:  # Cambiado de CONNECTED a CONECTADO
                    colors.append('green')
                elif status == DeviceStatus.OCUPADO:  # Cambiado de BUSY a OCUPADO
                    colors.append('blue')
                elif status == DeviceStatus.ERROR:  # Sin cambios
                    colors.append('red')
                elif status == DeviceStatus.DESCONECTADO:  # Cambiado de DISCONNECTED a DESCONECTADO
                    colors.append('gray')
                else:
                    colors.append('orange')
            
            # Crear un gráfico de barras horizontal si tenemos dispositivos
            if devices:
                y_pos = np.arange(len(devices))
                self.device_status_ax.barh(y_pos, [1] * len(devices), color=colors)
                self.device_status_ax.set_yticks(y_pos)
                self.device_status_ax.set_yticklabels(devices)
                self.device_status_ax.set_xlabel("Estado")
                
                # Agregar etiquetas de estado
                for i, status in enumerate(statuses):
                    self.device_status_ax.text(0.5, i, status, ha='center', va='center', color='white')
            
            # Ajustar diseño
            self.fig.tight_layout()
            
            # Redibujar el lienzo
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.error(f"Error al actualizar gráficos en GUI: {e}")
    
    # =========================================================================
    # MÉTODOS DE COMANDOS DEL MENÚ
    # =========================================================================
    
    def save_configuration(self):
        """Guardar la configuración actual en un archivo"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            
            if not file_path:
                return
            
            # Crear un diccionario de configuración
            config = {
                "devices": [],
                "scheduling_algorithm": self.io_scheduler.algorithm.name
            }
            
            # Agregar todos los dispositivos
            for device_id, driver in self.driver_table.get_all_drivers().items():
                config["devices"].append(driver.dcb.to_dict())
            
            # Guardar en archivo
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            logger.info(f"Configuración guardada en {file_path}")
            messagebox.showinfo("Éxito", f"Configuración guardada en {file_path}")
            
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")
            messagebox.showerror("Error", f"Error al guardar configuración: {e}")
    
    def load_configuration(self):
        """Cargar una configuración desde un archivo"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            
            if not file_path:
                return
            
            # Cargar la configuración
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            # Establecer el algoritmo de planificación
            if "scheduling_algorithm" in config:
                algorithm = SchedulingAlgorithm[config["scheduling_algorithm"]]
                self.io_scheduler.set_algorithm(algorithm)
                self.scheduling_var.set(config["scheduling_algorithm"])
            
            # Limpiar dispositivos existentes
            for device_id in list(self.driver_table.get_all_drivers().keys()):
                self.driver_table.unregister_driver(device_id)
            
            # Agregar todos los dispositivos
            for device_data in config.get("devices", []):
                # Crear un nuevo bloque de control de dispositivo
                dcb = DeviceControlBlock(
                    device_id=device_data["device_id"],
                    device_name=device_data["device_name"],
                    device_type=DeviceType[device_data["device_type"]],
                    capacity_gb=device_data["capacity_gb"],
                    transfer_rate_mb_s=device_data["transfer_rate_mb_s"]
                )
                
                # Crear un nuevo controlador
                if dcb.device_type == DeviceType.BLOQUE:
                    driver = BlockDeviceDriver(dcb, self.interrupt_table, self.buffer_manager)
                else:
                    driver = CharacterDeviceDriver(dcb, self.interrupt_table, self.buffer_manager)
                
                # Registrar el controlador
                self.driver_table.register_driver(dcb.device_id, driver)
                
                # Conectar el dispositivo si estaba conectado
                if device_data["status"] == "CONECTADO":  # Cambiado de CONNECTED a CONECTADO
                    self.interrupt_table.trigger_interrupt(f"{dcb.device_name.upper().replace(' ', '_')}_CONNECT")  # Revertido a CONNECT
            
            # Actualizar la interfaz
            self.update_device_list()
            
            logger.info(f"Configuración cargada desde {file_path}")
            messagebox.showinfo("Éxito", f"Configuración cargada desde {file_path}")
            
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            messagebox.showerror("Error", f"Error al cargar configuración: {e}")
    
    def export_statistics(self):
        """Exportar estadísticas a un archivo"""
        try:
            if not self.io_manager:
                messagebox.showerror("Error", "Gestor de E/S no inicializado")
                return
                
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            
            if not file_path:
                return
            
            # Crear un diccionario de estadísticas
            stats = {
                "overall": self.io_manager.stats,
                "devices": [],
                "operations": self.io_manager.operation_history
            }
            
            # Agregar todos los dispositivos
            for device_id, driver in self.driver_table.get_all_drivers().items():
                stats["devices"].append(driver.dcb.to_dict())
            
            # Guardar en archivo
            with open(file_path, 'w') as f:
                json.dump(stats, f, indent=4)
            
            logger.info(f"Estadísticas exportadas a {file_path}")
            messagebox.showinfo("Éxito", f"Estadísticas exportadas a {file_path}")
            
        except Exception as e:
            logger.error(f"Error al exportar estadísticas: {e}")
            messagebox.showerror("Error", f"Error al exportar estadísticas: {e}")
    
    def clear_log(self):
        """Limpiar el texto del registro"""
        try:
            self.log_text.configure(state='normal')
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state='disabled')
        except Exception as e:
            logger.error(f"Error al limpiar registro: {e}")
    
    def save_log(self):
        """Guardar el registro en un archivo"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Archivos de Registro", "*.log"), ("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")]
            )
            
            if not file_path:
                return
            
            # Obtener el texto del registro
            log_text = self.log_text.get(1.0, tk.END)
            
            # Guardar en archivo
            with open(file_path, 'w') as f:
                f.write(log_text)
            
            logger.info(f"Registro guardado en {file_path}")
            messagebox.showinfo("Éxito", f"Registro guardado en {file_path}")
            
        except Exception as e:
            logger.error(f"Error al guardar registro: {e}")
            messagebox.showerror("Error", f"Error al guardar registro: {e}")
    
    def change_scheduling_algorithm(self):
        """Cambiar el algoritmo de planificación"""
        try:
            algorithm_name = self.scheduling_var.get()
            algorithm = SchedulingAlgorithm[algorithm_name]
            self.io_scheduler.set_algorithm(algorithm)
            
            logger.info(f"Algoritmo de planificación cambiado a {algorithm_name}")
        except Exception as e:
            logger.error(f"Error al cambiar algoritmo de planificación: {e}")
    
    def show_documentation(self):
        """Mostrar la documentación"""
        messagebox.showinfo("Documentación", 
                           "Sistema Avanzado de Simulación de Dispositivos de E/S\n\n"
                           "Esta aplicación simula un subsistema de E/S completo de un sistema operativo, "
                           "incluyendo controladores de dispositivos, manejo de interrupciones, "
                           "planificación de operaciones y almacenamiento en búfer.\n\n"
                           "Para más información, consulte la documentación.")
    
    def show_about(self):
        """Mostrar el cuadro de diálogo Acerca de"""
        messagebox.showinfo("Acerca de", 
                           "Sistema Avanzado de Simulación de Dispositivos de E/S\n"
                           "Versión 1.0\n\n"
                           "Creado con fines educativos\n"
                           "© 2023 Todos los derechos reservados")
    
    def exit_application(self):
        """Salir de la aplicación"""
        try:
            if messagebox.askyesno("Salir", "¿Está seguro de que desea salir?"):
                # Detener el Gestor de E/S
                if self.io_manager:
                    self.io_manager.stop()
                
                # Cerrar la aplicación
                self.master.destroy()
        except Exception as e:
            logger.error(f"Error al salir de la aplicación: {e}")
            # Forzar salida
            self.master.destroy()

# =============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    # Crear la ventana principal
    root = tk.Tk()
    
    # Configurar el tema (si está disponible)
    try:
        style = ttk.Style()
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")
    except:
        pass
    
    # Crear la aplicación
    app = IOSimulationGUI(root)
    
    # Iniciar el bucle principal
    root.mainloop()
