"""
Sistema Avanzado de Simulación de Dispositivos de E/S - Componentes Principales

Este módulo contiene los componentes principales para simular dispositivos de E/S, 
controladores de dispositivos, manejo de interrupciones y planificación de operaciones.
"""

import time
import random
import threading
import logging
from queue import Queue, PriorityQueue
import uuid
from enum import Enum, auto
from typing import Dict, List, Tuple, Any, Optional, Callable

# Configurar el registro
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("io_simulation.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SimulaciónE/S")

# =============================================================================
# ENUMS Y CONSTANTES
# =============================================================================

class DeviceType(Enum):
    BLOQUE = auto()
    CARACTER = auto()

class OperationType(Enum):
    LECTURA = auto()
    ESCRITURA = auto()
    CONTROL = auto()
    BUSQUEDA = auto()

class DeviceStatus(Enum):
    DESCONECTADO = auto()
    CONECTADO = auto()
    OCUPADO = auto()
    ERROR = auto()
    EN_ESPERA = auto()

class SchedulingAlgorithm(Enum):
    FIFO = auto()
    PRIORIDAD = auto()
    TRABAJO_MAS_CORTO_PRIMERO = auto()
    ROUND_ROBIN = auto()

# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

class DeviceControlBlock:
    """
    Simula el Bloque de Control de Dispositivos (DCB) que contiene metadatos sobre un dispositivo.
    En un sistema operativo real, esto contendría punteros a estructuras de datos específicas del dispositivo.
    """
    def __init__(self, device_id: int, device_name: str, device_type: DeviceType, 
                 capacity_gb: float = 0, transfer_rate_mb_s: float = 0):
        self.device_id = device_id
        self.device_name = device_name
        self.device_type = device_type
        self.capacity_gb = capacity_gb
        self.transfer_rate_mb_s = transfer_rate_mb_s
        self.status = DeviceStatus.DESCONECTADO
        self.current_position = 0  # Para dispositivos de bloques
        self.error_count = 0
        self.operations_completed = 0
        self.bytes_transferred = 0
        self.last_operation_time = 0
        self.creation_time = time.time()
        
    def __str__(self):
        return (f"[DCB] {self.device_name} (ID: {self.device_id}, "
                f"Tipo: {self.device_type.name}, Estado: {self.status.name})")
    
    def to_dict(self):
        """Convertir el DCB a un diccionario para su serialización"""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type.name,
            "capacity_gb": self.capacity_gb,
            "transfer_rate_mb_s": self.transfer_rate_mb_s,
            "status": self.status.name,
            "operations_completed": self.operations_completed,
            "bytes_transferred": self.bytes_transferred,
            "error_count": self.error_count
        }

class IOOperation:
    """
    Representa una operación de E/S en la cola de E/S.
    Contiene el tipo de operación, tamaño de datos, información del proceso y prioridad.
    """
    def __init__(self, operation_type: OperationType, data_size_mb: float, 
                 process_name: str, priority: int = 0, block_address: int = None):
        self.operation_id = str(uuid.uuid4())[:8]  # Generar ID único
        self.operation_type = operation_type
        self.data_size_mb = data_size_mb
        self.process_name = process_name
        self.priority = priority
        self.block_address = block_address  # Para dispositivos de bloques
        self.creation_time = time.time()
        self.start_time = None
        self.completion_time = None
        self.status = "PENDIENTE"
        
    def __str__(self):
        return (f"[IOOperation] ID: {self.operation_id}, Tipo: {self.operation_type.name}, "
                f"Tamaño: {self.data_size_mb} MB, Proceso: {self.process_name}, "
                f"Prioridad: {self.priority}, Estado: {self.status}")
    
    def __lt__(self, other):
        # Para comparación en cola de prioridad
        return self.priority > other.priority  # Número más alto = mayor prioridad

class InterruptTable:
    """
    Simula una Tabla de Interrupciones que asigna tipos de interrupciones a funciones manejadoras.
    En un sistema operativo real, esto contendría punteros a rutinas de servicio de interrupciones.
    """
    def __init__(self):
        self.interrupt_handlers = {}
        self.interrupt_history = []
        self.interrupt_stats = {}
        
    def register_interrupt_handler(self, interrupt_type: str, handler: Callable):
        """Registrar una función manejadora para un tipo específico de interrupción"""
        self.interrupt_handlers[interrupt_type] = handler
        self.interrupt_stats[interrupt_type] = {
            "count": 0,
            "last_triggered": None
        }
        logger.info(f"Manejador registrado para interrupción: {interrupt_type}")
        
    def trigger_interrupt(self, interrupt_type: str, *args, **kwargs):
        """Activar una interrupción llamando a su función manejadora"""
        logger.info(f"Interrupción activada: {interrupt_type}")
        
        # Registrar interrupción en el historial
        interrupt_info = {
            "type": interrupt_type,
            "time": time.time(),
            "args": args,
            "kwargs": kwargs
        }
        self.interrupt_history.append(interrupt_info)
        
        # Actualizar estadísticas
        if interrupt_type in self.interrupt_stats:
            self.interrupt_stats[interrupt_type]["count"] += 1
            self.interrupt_stats[interrupt_type]["last_triggered"] = time.time()
        
        # Llamar al manejador si está registrado
        if interrupt_type in self.interrupt_handlers:
            try:
                self.interrupt_handlers[interrupt_type](*args, **kwargs)
            except Exception as e:
                logger.error(f"Error en el manejador de interrupción para {interrupt_type}: {e}")
        else:
            logger.warning(f"No hay manejador registrado para la interrupción: {interrupt_type}")

class Buffer:
    """
    Simula un búfer de memoria para operaciones de E/S.
    En un sistema operativo real, esto sería una región de memoria para almacenamiento temporal de datos.
    """
    def __init__(self, size_kb: int):
        self.size_kb = size_kb
        self.used_kb = 0
        self.data = {}  # Almacenamiento de datos simulado
        
    def allocate(self, size_kb: int, operation_id: str) -> bool:
        """Intentar asignar espacio de búfer para una operación"""
        if self.used_kb + size_kb <= self.size_kb:
            self.used_kb += size_kb
            self.data[operation_id] = {
                "size": size_kb,
                "content": f"Datos simulados para la operación {operation_id}"
            }
            return True
        return False
    
    def release(self, operation_id: str) -> bool:
        """Liberar espacio de búfer asignado para una operación"""
        if operation_id in self.data:
            self.used_kb -= self.data[operation_id]["size"]
            del self.data[operation_id]
            return True
        return False
    
    def get_usage_percentage(self) -> float:
        """Devolver el porcentaje de espacio de búfer actualmente en uso"""
        return (self.used_kb / self.size_kb) * 100 if self.size_kb > 0 else 0

# =============================================================================
# CONTROLADORES DE DISPOSITIVOS
# =============================================================================

class DeviceDriver:
    """
    Clase base para controladores de dispositivos. Maneja la funcionalidad común para todos los tipos de dispositivos.
    """
    def __init__(self, device_control_block: DeviceControlBlock, 
                 interrupt_table: InterruptTable, buffer_manager: 'BufferManager'):
        self.dcb = device_control_block
        self.interrupt_table = interrupt_table
        self.buffer_manager = buffer_manager
        self.operation_history = []
        
    def perform_operation(self, io_operation: IOOperation) -> bool:
        """Método base para realizar operaciones de E/S"""
        if self.dcb.status != DeviceStatus.CONECTADO:
            logger.error(f"Dispositivo {self.dcb.device_name} no conectado o en estado de error")
            return False
        
        # Marcar operación como iniciada
        io_operation.start_time = time.time()
        io_operation.status = "EN_PROGRESO"
        
        # Registrar operación en el historial
        self.operation_history.append(io_operation)
        
        return True
    
    def complete_operation(self, io_operation: IOOperation, success: bool = True):
        """Marcar una operación como completada"""
        io_operation.completion_time = time.time()
        io_operation.status = "COMPLETADA" if success else "FALLIDA"
        
        if success:
            self.dcb.operations_completed += 1
            self.dcb.bytes_transferred += io_operation.data_size_mb * 1024 * 1024  # Convertir MB a bytes
            self.dcb.last_operation_time = time.time()
        else:
            self.dcb.error_count += 1
            
        # Liberar cualquier búfer asignado
        self.buffer_manager.release_buffer(io_operation.operation_id)
        
        # Activar interrupción de finalización
        interrupt_type = f"{self.dcb.device_name.upper().replace(' ', '_')}_OPERATION_COMPLETED"
        self.interrupt_table.trigger_interrupt(interrupt_type, io_operation, success)

class BlockDeviceDriver(DeviceDriver):
    """
    Controlador para dispositivos de bloques como discos, unidades USB, etc.
    Maneja operaciones orientadas a bloques con capacidades de búsqueda.
    """
    def __init__(self, device_control_block: DeviceControlBlock, 
                 interrupt_table: InterruptTable, buffer_manager: 'BufferManager'):
        super().__init__(device_control_block, interrupt_table, buffer_manager)
        
        # Registrar manejadores de interrupciones específicos del dispositivo
        device_name_upper = self.dcb.device_name.upper().replace(' ', '_')
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_CONNECT", self.on_connect)  # Revertido a CONNECT
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_DISCONNECT", self.on_disconnect)  # Revertido a DISCONNECT
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_ERROR", self.on_error)
    
    def on_connect(self):
        """Manejador para interrupción de conexión de dispositivo"""
        logger.info(f"[{self.dcb.device_name}] Dispositivo conectado")
        self.dcb.status = DeviceStatus.CONECTADO
    
    def on_disconnect(self):
        """Manejador para interrupción de desconexión de dispositivo"""
        logger.info(f"[{self.dcb.device_name}] Dispositivo desconectado")
        self.dcb.status = DeviceStatus.DESCONECTADO
    
    def on_error(self, error_code: int = 0, error_message: str = "Error desconocido"):
        """Manejador para interrupción de error de dispositivo"""
        logger.error(f"[{self.dcb.device_name}] Error de dispositivo: {error_message} (código: {error_code})")
        self.dcb.status = DeviceStatus.ERROR
        self.dcb.error_count += 1
    
    def perform_operation(self, io_operation: IOOperation) -> bool:
        """Realizar una operación de dispositivo de bloques (lectura/escritura/búsqueda)"""
        if not super().perform_operation(io_operation):
            return False
            
        try:
            # Establecer estado del dispositivo como ocupado
            self.dcb.status = DeviceStatus.OCUPADO
            
            # Asignar búfer si es necesario
            if not self.buffer_manager.allocate_buffer(io_operation.data_size_mb, io_operation.operation_id):
                logger.error(f"Falló la asignación de búfer para la operación {io_operation.operation_id}")
                self.complete_operation(io_operation, False)
                return False
            
            # Simular búsqueda si se especifica dirección de bloque
            seek_time = 0
            if io_operation.block_address is not None:
                seek_distance = abs(self.dcb.current_position - io_operation.block_address)
                seek_time = seek_distance * 0.001  # Simular tiempo de búsqueda (1ms por cada 1000 bloques)
                self.dcb.current_position = io_operation.block_address
                time.sleep(seek_time)
            
            # Calcular tiempo de transferencia basado en la tasa de transferencia del dispositivo
            transfer_time = io_operation.data_size_mb / self.dcb.transfer_rate_mb_s
            
            # Simular el tiempo de operación
            logger.info(f"[{self.dcb.device_name}] Operación de {io_operation.operation_type.name} iniciada: "
                       f"{io_operation.data_size_mb} MB, tiempo estimado: {transfer_time:.2f}s")
            
            # Simular errores potenciales (5% de probabilidad)
            if random.random() < 0.05:
                time.sleep(transfer_time / 3)  # Operación parcial antes del error
                raise IOError("Error de E/S simulado")
                
            time.sleep(transfer_time)
            
            logger.info(f"[{self.dcb.device_name}] Operación completada exitosamente")
            
            # Marcar operación como completada
            self.complete_operation(io_operation, True)
            
            # Establecer estado del dispositivo como conectado
            self.dcb.status = DeviceStatus.CONECTADO
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.dcb.device_name}] Operación fallida: {e}")
            self.complete_operation(io_operation, False)
            self.dcb.status = DeviceStatus.ERROR
            return False

class CharacterDeviceDriver(DeviceDriver):
    """
    Controlador para dispositivos de caracteres como teclados, ratones, puertos seriales, etc.
    Maneja operaciones orientadas a flujo sin búsqueda.
    """
    def __init__(self, device_control_block: DeviceControlBlock, 
                 interrupt_table: InterruptTable, buffer_manager: 'BufferManager'):
        super().__init__(device_control_block, interrupt_table, buffer_manager)
        
        # Registrar manejadores de interrupciones específicos del dispositivo
        device_name_upper = self.dcb.device_name.upper().replace(' ', '_')
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_CONNECT", self.on_connect)  # Revertido a CONNECT
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_DISCONNECT", self.on_disconnect)  # Revertido a DISCONNECT
        self.interrupt_table.register_interrupt_handler(
            f"{device_name_upper}_DATA_AVAILABLE", self.on_data_available)
    
    def on_connect(self):
        """Manejador para interrupción de conexión de dispositivo"""
        logger.info(f"[{self.dcb.device_name}] Dispositivo conectado")
        self.dcb.status = DeviceStatus.CONECTADO
    
    def on_disconnect(self):
        """Manejador para interrupción de desconexión de dispositivo"""
        logger.info(f"[{self.dcb.device_name}] Dispositivo desconectado")
        self.dcb.status = DeviceStatus.DESCONECTADO
        self.interrupt_table.trigger_interrupt(f"{self.dcb.device_name.upper().replace(' ', '_')}_DISCONNECT")  # Revertido a DISCONNECT
    
    def on_data_available(self, data_size: float = 0):
        """Manejador para interrupción de datos disponibles"""
        logger.info(f"[{self.dcb.device_name}] Datos disponibles: {data_size} MB")
    
    def perform_operation(self, io_operation: IOOperation) -> bool:
        """Realizar una operación de dispositivo de caracteres (lectura/escritura)"""
        if not super().perform_operation(io_operation):
            return False
            
        try:
            # Establecer estado del dispositivo como ocupado
            self.dcb.status = DeviceStatus.OCUPADO
            
            # Los dispositivos de caracteres no necesitan búsqueda
            # Calcular tiempo de transferencia basado en la tasa de transferencia del dispositivo
            transfer_time = io_operation.data_size_mb / self.dcb.transfer_rate_mb_s
            
            # Simular el tiempo de operación
            logger.info(f"[{self.dcb.device_name}] Operación de {io_operation.operation_type.name} iniciada: "
                       f"{io_operation.data_size_mb} MB, tiempo estimado: {transfer_time:.2f}s")
            
            # Simular errores potenciales (3% de probabilidad para dispositivos de caracteres)
            if random.random() < 0.03:
                time.sleep(transfer_time / 2)  # Operación parcial antes del error
                raise IOError("Error de E/S simulado")
                
            time.sleep(transfer_time)
            
            logger.info(f"[{self.dcb.device_name}] Operación completada exitosamente")
            
            # Marcar operación como completada
            self.complete_operation(io_operation, True)
            
            # Establecer estado del dispositivo como conectado
            self.dcb.status = DeviceStatus.CONECTADO
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.dcb.device_name}] Operación fallida: {e}")
            self.complete_operation(io_operation, False)
            self.dcb.status = DeviceStatus.ERROR
            self.interrupt_table.trigger_interrupt(f"{self.dcb.device_name.upper().replace(' ', '_')}_ERROR", error_code=random.randint(1, 100), error_message="Error simulado")
            return False

# =============================================================================
# GESTIÓN DE DISPOSITIVOS
# =============================================================================

class DeviceDriverTable:
    """
    Mantiene un registro de controladores de dispositivos indexados por ID de dispositivo.
    """
    def __init__(self):
        self.drivers = {}
    
    def register_driver(self, device_id: int, driver_instance: DeviceDriver):
        """Registrar un controlador para un ID de dispositivo específico"""
        self.drivers[device_id] = driver_instance
        logger.info(f"Controlador registrado para ID de dispositivo {device_id}: {driver_instance.dcb.device_name}")
    
    def get_driver(self, device_id: int) -> Optional[DeviceDriver]:
        """Obtener la instancia del controlador para un ID de dispositivo específico"""
        return self.drivers.get(device_id)
    
    def unregister_driver(self, device_id: int) -> bool:
        """Desregistrar un controlador para un ID de dispositivo específico"""
        if device_id in self.drivers:
            del self.drivers[device_id]
            logger.info(f"Controlador desregistrado para ID de dispositivo {device_id}")
            return True
        return False
    
    def get_all_drivers(self) -> Dict[int, DeviceDriver]:
        """Obtener todos los controladores registrados"""
        return self.drivers

class BufferManager:
    """
    Administra búferes de memoria para operaciones de E/S.
    """
    def __init__(self, total_buffer_size_kb: int = 1024):
        self.total_buffer_size_kb = total_buffer_size_kb
        self.buffers = {}  # operation_id -> Buffer
        self.used_buffer_kb = 0
        
    def allocate_buffer(self, size_mb: float, operation_id: str) -> bool:
        """Asignar un búfer para una operación de E/S"""
        size_kb = int(size_mb * 1024)
        
        # Verificar si tenemos suficiente espacio
        if self.used_buffer_kb + size_kb > self.total_buffer_size_kb:
            logger.warning(f"Falló la asignación de búfer: No hay suficiente espacio para {size_kb} KB")
            return False
        
        # Crear un nuevo búfer
        buffer = Buffer(size_kb)
        buffer.allocate(size_kb, operation_id)
        
        # Almacenar el búfer
        self.buffers[operation_id] = buffer
        self.used_buffer_kb += size_kb
        
        logger.debug(f"Búfer asignado: {size_kb} KB para la operación {operation_id}")
        return True
    
    def release_buffer(self, operation_id: str) -> bool:
        """Liberar un búfer asignado para una operación de E/S"""
        if operation_id in self.buffers:
            buffer = self.buffers[operation_id]
            self.used_buffer_kb -= buffer.size_kb
            del self.buffers[operation_id]
            logger.debug(f"Búfer liberado para la operación {operation_id}")
            return True
        return False
    
    def get_buffer_usage(self) -> float:
        """Obtener el porcentaje de espacio de búfer actualmente en uso"""
        return (self.used_buffer_kb / self.total_buffer_size_kb) * 100 if self.total_buffer_size_kb > 0 else 0

# =============================================================================
# PLANIFICACIÓN Y GESTIÓN DE E/S
# =============================================================================

class IOScheduler:
    """
    Implementa diferentes algoritmos de planificación de E/S.
    """
    def __init__(self, algorithm: SchedulingAlgorithm = SchedulingAlgorithm.FIFO):
        self.algorithm = algorithm
        self.operation_queues = {}  # device_id -> Queue
        
    def set_algorithm(self, algorithm: SchedulingAlgorithm):
        """Cambiar el algoritmo de planificación"""
        self.algorithm = algorithm
        
        # Recrear colas con el nuevo algoritmo
        new_queues = {}
        for device_id, old_queue in self.operation_queues.items():
            # Crear una nueva cola basada en el algoritmo
            if algorithm == SchedulingAlgorithm.FIFO:
                new_queue = Queue()
            elif algorithm == SchedulingAlgorithm.PRIORIDAD:
                new_queue = PriorityQueue()
            else:
                new_queue = Queue()  # Por defecto FIFO
                
            # Transferir elementos de la cola antigua a la nueva
            while not old_queue.empty():
                item = old_queue.get()
                new_queue.put(item)
                
            new_queues[device_id] = new_queue
            
        self.operation_queues = new_queues
        logger.info(f"Algoritmo de planificación cambiado a {algorithm.name}")
    
    def add_operation(self, device_id: int, io_operation: IOOperation):
        """Agregar una operación a la cola para un dispositivo específico"""
        # Crear cola para el dispositivo si no existe
        if device_id not in self.operation_queues:
            if self.algorithm == SchedulingAlgorithm.FIFO:
                self.operation_queues[device_id] = Queue()
            elif self.algorithm == SchedulingAlgorithm.PRIORIDAD:
                self.operation_queues[device_id] = PriorityQueue()
            else:
                self.operation_queues[device_id] = Queue()  # Por defecto FIFO
        
        # Agregar operación a la cola
        self.operation_queues[device_id].put(io_operation)
        logger.info(f"Operación agregada a la cola para el dispositivo {device_id}: {io_operation}")
    
    def get_next_operation(self, device_id: int) -> Optional[IOOperation]:
        """Obtener la siguiente operación para un dispositivo específico basado en el algoritmo de planificación"""
        if device_id not in self.operation_queues or self.operation_queues[device_id].empty():
            return None
            
        # Obtener la siguiente operación basada en el algoritmo
        if self.algorithm == SchedulingAlgorithm.FIFO:
            return self.operation_queues[device_id].get()
        elif self.algorithm == SchedulingAlgorithm.PRIORIDAD:
            return self.operation_queues[device_id].get()
        elif self.algorithm == SchedulingAlgorithm.TRABAJO_MAS_CORTO_PRIMERO:
            # Para SJF, necesitamos encontrar el trabajo más corto
            # Esta es una implementación simplificada que no mantiene el orden de la cola
            queue = self.operation_queues[device_id]
            operations = []
            while not queue.empty():
                operations.append(queue.get())
                
            if not operations:
                return None
                
            # Encontrar el trabajo más corto
            shortest_op = min(operations, key=lambda op: op.data_size_mb)
            
            # Poner las otras operaciones de vuelta en la cola
            for op in operations:
                if op != shortest_op:
                    queue.put(op)
                    
            return shortest_op
        else:
            # Por defecto FIFO
            return self.operation_queues[device_id].get()
    
    def get_queue_length(self, device_id: int) -> int:
        """Obtener el número de operaciones en la cola para un dispositivo específico"""
        if device_id not in self.operation_queues:
            return 0
        return self.operation_queues[device_id].qsize()

class IOManager(threading.Thread):
    """
    Administra operaciones de E/S procesando operaciones en cola y delegándolas a los controladores de dispositivos.
    """
    def __init__(self, driver_table: DeviceDriverTable, io_scheduler: IOScheduler):
        super().__init__()
        self.daemon = True
        self.driver_table = driver_table
        self.io_scheduler = io_scheduler
        self.running = True
        self.stats = {
            "operations_processed": 0,
            "operations_succeeded": 0,
            "operations_failed": 0,
            "total_data_mb": 0,
            "start_time": time.time()
        }
        self.operation_history = []
        self.status_listeners = []
        
    def run(self):
        """Bucle principal de procesamiento"""
        logger.info("Gestor de E/S iniciado")
        
        while self.running:
            try:
                # Procesar operaciones para todos los dispositivos
                for device_id in list(self.driver_table.get_all_drivers().keys()):
                    # Obtener el controlador para este dispositivo
                    driver = self.driver_table.get_driver(device_id)
                    
                    # Saltar si no se encuentra el controlador o el dispositivo está ocupado
                    if not driver or driver.dcb.status == DeviceStatus.OCUPADO:
                        continue
                    
                    # Obtener la siguiente operación para este dispositivo
                    io_operation = self.io_scheduler.get_next_operation(device_id)
                    
                    # Procesar la operación si hay una disponible
                    if io_operation:
                        self.stats["operations_processed"] += 1
                        
                        # Realizar la operación
                        success = driver.perform_operation(io_operation)
                        
                        # Actualizar estadísticas
                        if success:
                            self.stats["operations_succeeded"] += 1
                            self.stats["total_data_mb"] += io_operation.data_size_mb
                        else:
                            self.stats["operations_failed"] += 1
                        
                        # Agregar al historial de operaciones
                        op_record = {
                            "operation_id": io_operation.operation_id,
                            "device_id": device_id,
                            "device_name": driver.dcb.device_name,
                            "operation_type": io_operation.operation_type.name,
                            "data_size_mb": io_operation.data_size_mb,
                            "process_name": io_operation.process_name,
                            "priority": io_operation.priority,
                            "creation_time": io_operation.creation_time,
                            "start_time": io_operation.start_time,
                            "completion_time": io_operation.completion_time,
                            "status": io_operation.status,
                            "success": success
                        }
                        self.operation_history.append(op_record)
                        
                        # Notificar a los oyentes de estado
                        for listener in self.status_listeners:
                            try:
                                listener(device_id, io_operation, success)
                            except Exception as e:
                                logger.error(f"Error en el oyente de estado: {e}")
                
                # Dormir brevemente para evitar consumo excesivo de CPU
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error en el Gestor de E/S: {e}")
                time.sleep(1)  # Dormir más tiempo en caso de error
    
    def stop(self):
        """Detener el Gestor de E/S"""
        logger.info("Deteniendo el Gestor de E/S")
        self.running = False
        
    def add_io_operation(self, device_id: int, io_operation: IOOperation):
        """Agregar una operación de E/S al planificador"""
        self.io_scheduler.add_operation(device_id, io_operation)
        
    def add_status_listener(self, listener: Callable):
        """Agregar un oyente para ser notificado de cambios en el estado de las operaciones"""
        self.status_listeners.append(listener)
        
    def get_throughput(self) -> float:
        """Calcular el rendimiento en MB/s"""
        elapsed_time = time.time() - self.stats["start_time"]
        if elapsed_time > 0:
            return self.stats["total_data_mb"] / elapsed_time
        return 0
        
    def get_success_rate(self) -> float:
        """Calcular la tasa de éxito como porcentaje"""
        total = self.stats["operations_succeeded"] + self.stats["operations_failed"]
        if total > 0:
            return (self.stats["operations_succeeded"] / total) * 100
        return 0

# Función de prueba simple para verificar la funcionalidad principal
def test_core_functionality():
    """Prueba la funcionalidad principal del sistema"""
    # Crear los componentes principales
    interrupt_table = InterruptTable()
    buffer_manager = BufferManager(2048)  # Búfer de 2MB
    driver_table = DeviceDriverTable()
    io_scheduler = IOScheduler(SchedulingAlgorithm.FIFO)
    
    # Crear una unidad USB
    usb_dcb = DeviceControlBlock(
        device_id=1,
        device_name="Unidad USB",
        device_type=DeviceType.BLOQUE,
        capacity_gb=128,
        transfer_rate_mb_s=30.0
    )
    usb_driver = BlockDeviceDriver(usb_dcb, interrupt_table, buffer_manager)
    driver_table.register_driver(usb_dcb.device_id, usb_driver)
    
    # Conectar la unidad USB
    interrupt_table.trigger_interrupt("UNIDAD_USB_CONNECT")  # Revertido a CONNECT
    
    # Crear e iniciar el Gestor de E/S
    io_manager = IOManager(driver_table, io_scheduler)
    io_manager.start()
    
    # Crear una operación de E/S
    operation = IOOperation(
        operation_type=OperationType.LECTURA,
        data_size_mb=10.0,
        process_name="ProcesoPrueba",
        priority=5
    )
    
    # Agregar la operación a la cola
    io_manager.add_io_operation(usb_dcb.device_id, operation)
    
    # Esperar a que la operación se complete
    time.sleep(1)
    
    # Detener el Gestor de E/S
    io_manager.stop()
    
    print("Prueba de funcionalidad principal completada")

if __name__ == "__main__":
    test_core_functionality()
