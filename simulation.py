from collections import defaultdict
from functools import reduce
from scipy.stats import halfnorm, logistic, lognorm, truncnorm


class SimulationResult:
    def __init__(self, workers_factura, workers_detalle, pps_factura, pps_detalle, pto_workers_factura, pto_workers_detalle, porcentaje_sol_factura_atendidas_por_workers_detalle):
        self.workers_factura = workers_factura
        self.workers_detalle = workers_detalle
        self.pps_factura = pps_factura
        self.pps_detalle = pps_detalle
        self.pto_workers_factura = pto_workers_factura
        self.pto_workers_detalle = pto_workers_detalle
        self.porcentaje_sol_factura_atendidas_por_workers_detalle = porcentaje_sol_factura_atendidas_por_workers_detalle

    def print(self):
        print(f"Workers factura: {self.workers_factura}")
        print(f"Workers detalle: {self.workers_detalle}")
        print(f"PPS Solicitud de facturas: {self.pps_factura:.2f}s")
        print(f"PPS Solicitud de Detalle:  {self.pps_detalle:.2f}s")
        print(f"Porcentaje de solicitudes de factura atendidas por workers de detalle: {self.porcentaje_sol_factura_atendidas_por_workers_detalle:.2f}%")
        
        for key, value in self.pto_workers_factura.items():
            print(f"Porcentaje de tiempo ocioso del worker de factura {key}: \t {value:.2f}%")
        
        for key, value in self.pto_workers_detalle.items():
            print(f"Porcentaje de tiempo ocioso del worker de detalle {key}: \t {value:.2f}%")

class Simulation:
    def __init__(self, workers_factura, workers_detalle, tiempo_final):
        self.workers_factura = workers_factura
        self.workers_detalle = workers_detalle
        self.tiempo_final = tiempo_final

        self.tiempo = 0.0
        self.tpll_sol_facturas = 0.0
        self.tpll_sol_detalle = 0.0

        self.tot_sol_facturas = 0
        self.tot_sol_detalle = 0

        self.TPS_workers_factura = {i: float('inf') for i in range(workers_factura)}
        self.TPS_workers_detalle = {i: float('inf') for i in range(workers_detalle)}

        self.ITOWorkersFactura = {i: 0.0 for i in range(workers_factura)}
        self.ITOWorkersDetalle = {i: 0.0 for i in range(workers_detalle)}
        self.STOWorkersFactura = {i: 0.0 for i in range(workers_factura)}
        self.STOWorkersDetalle = {i: 0.0 for i in range(workers_detalle)}

        self.NS_facturas = 0
        self.NS_detalle = 0

        self.STLL_sol_facturas = 0.0
        self.STLL_sol_detalle = 0.0

        self.STS_detalle = 0.0
        self.STS_facturas = 0.0

        self.worker_factura_was_used = {i: False for i in range(workers_factura)}
        self.worker_detalle_was_used = {i: False for i in range(workers_detalle)}

        self.solicitudes_factura_atendidas_por_workers_detalle = 0

    def exec(self):
        print("Simulacion iniciada")
        
        while self.tiempo < self.tiempo_final:
            if self.min_time() == self.tpll_sol_facturas:
                self.llegada_sol_factura()
            elif self.min_time() == self.tpll_sol_detalle:
                self.llegada_sol_detalle()
            elif self.min_time() == self.min_TPS_workers_detalle()[1]:
                self.salida_worker_detalle()
            elif self.min_time() == self.min_TPS_workers_factura()[1]:
                self.salida_worker_factura()
        
        while self.min_TPS_workers_detalle()[1] != float('inf') or self.min_TPS_workers_factura()[1] != float('inf'):
            self.tpll_sol_detalle = float('inf')
            self.tpll_sol_facturas = float('inf')
            if self.min_time() == self.min_TPS_workers_detalle()[1]:
                self.salida_worker_detalle()
            elif self.min_time() == self.min_TPS_workers_factura()[1]:
                self.salida_worker_factura()

        PPS_factura = (self.STS_facturas - self.STLL_sol_facturas) / self.tot_sol_facturas
        PPS_detalle = (self.STS_detalle - self.STLL_sol_detalle) / self.tot_sol_detalle

        for key, value in self.worker_detalle_was_used.items():
            if not value:
                self.STOWorkersDetalle[key] = self.tiempo

        for key, value in self.worker_factura_was_used.items():
            if not value:
                self.STOWorkersFactura[key] = self.tiempo

        PTOWorkersFactura = {k: 100.0 * v / self.tiempo for k, v in self.STOWorkersFactura.items()}
        PTOWorkersDetalle = {k: 100.0 * v / self.tiempo for k, v in self.STOWorkersDetalle.items()}
        porcentaje_sol_factura_atendidas_por_workers_detalle = (self.solicitudes_factura_atendidas_por_workers_detalle / self.tot_sol_facturas) * 100.0

        return SimulationResult(self.workers_factura, self.workers_detalle, PPS_factura, PPS_detalle, PTOWorkersFactura, PTOWorkersDetalle, porcentaje_sol_factura_atendidas_por_workers_detalle)

    def llegada_sol_factura(self):
        self.tiempo = self.tpll_sol_facturas
        self.tpll_sol_facturas = self.tiempo + self.IA_facturas()
        self.NS_facturas += 1
        self.tot_sol_facturas += 1
        self.STLL_sol_facturas += self.tiempo
        if self.NS_facturas <= self.workers_factura:
            free_worker = self.worker_factura_TPS_en_HV()
            self.STOWorkersFactura[free_worker] += self.tiempo - self.ITOWorkersFactura[free_worker]
            TPS = self.tiempo + self.TA_factura()
            self.STS_facturas += TPS
            self.TPS_workers_factura[free_worker] = TPS
            self.worker_factura_was_used[free_worker] = True
        elif self.NS_detalle < self.workers_detalle:
            free_worker = self.worker_detalle_TPS_en_HV()
            self.NS_facturas -= 1
            self.NS_detalle += 1
            self.solicitudes_factura_atendidas_por_workers_detalle += 1
            self.STOWorkersDetalle[free_worker] += self.tiempo - self.ITOWorkersDetalle[free_worker]
            TPS = self.tiempo + self.TA_factura()
            self.STS_facturas += TPS
            self.TPS_workers_detalle[free_worker] = TPS
            self.worker_detalle_was_used[free_worker] = True

    def llegada_sol_detalle(self):
        self.tiempo = self.tpll_sol_detalle
        self.tpll_sol_detalle = self.tiempo + self.IA_detalle()
        self.tot_sol_detalle += 1
        self.NS_detalle += 1
        self.STLL_sol_detalle += self.tiempo
        if self.NS_detalle <= self.workers_detalle:
            free_worker = self.worker_detalle_TPS_en_HV()
            self.STOWorkersDetalle[free_worker] += self.tiempo - self.ITOWorkersDetalle[free_worker]
            TPS = self.tiempo + self.TA_detalle()
            self.STS_detalle += TPS
            self.TPS_workers_detalle[free_worker] = TPS
            self.worker_detalle_was_used[free_worker] = True

    def salida_worker_factura(self):
        self.NS_facturas -= 1
        newly_free_worker = self.min_TPS_workers_factura()
        self.tiempo = newly_free_worker[1]
        if self.NS_facturas >= self.workers_factura:
            TPS = self.tiempo + self.TA_factura()
            self.STS_facturas += TPS
            self.TPS_workers_factura[newly_free_worker[0]] = TPS
            self.worker_factura_was_used[newly_free_worker[0]] = True
        else:
            self.ITOWorkersFactura[newly_free_worker[0]] = self.tiempo
            self.TPS_workers_factura[newly_free_worker[0]] = float('inf')

    def salida_worker_detalle(self):
        self.NS_detalle -= 1
        newly_free_worker = self.min_TPS_workers_detalle()
        self.tiempo = newly_free_worker[1]
        if self.NS_detalle >= self.workers_detalle:
            TPS = self.tiempo + self.TA_detalle()
            self.STS_detalle += TPS
            self.TPS_workers_detalle[newly_free_worker[0]] = TPS
            self.worker_detalle_was_used[newly_free_worker[0]] = True
        elif self.NS_facturas > self.workers_factura:
            self.NS_detalle += 1
            self.NS_facturas -= 1
            self.solicitudes_factura_atendidas_por_workers_detalle += 1
            TPS = self.tiempo + self.TA_factura()
            self.STS_facturas += TPS
            self.TPS_workers_detalle[newly_free_worker[0]] = TPS
            self.worker_detalle_was_used[newly_free_worker[0]] = True
        else:
            self.ITOWorkersDetalle[newly_free_worker[0]] = self.tiempo
            self.TPS_workers_detalle[newly_free_worker[0]] = float('inf')

    def min_TPS_workers_factura(self):
        if(len(self.TPS_workers_factura) == 0): return (0, float('inf'))
        return min(self.TPS_workers_factura.items(), key=lambda x: x[1])

    def min_TPS_workers_detalle(self):
        return min(self.TPS_workers_detalle.items(), key=lambda x: x[1])

    def min_time(self):
        times = [self.tpll_sol_detalle, self.tpll_sol_facturas, self.min_TPS_workers_detalle()[1], self.min_TPS_workers_factura()[1]]
        return min(times)

    def worker_factura_TPS_en_HV(self):
        return next(k for k, v in self.TPS_workers_factura.items() if v == float('inf'))

    def worker_detalle_TPS_en_HV(self):
        return next(k for k, v in self.TPS_workers_detalle.items() if v == float('inf'))

    def IA_facturas(self):
        val = halfnorm.rvs(loc=-6.96763e-10, scale=9.64335)
        return val

    def IA_detalle(self):
        val = truncnorm.rvs(a = 0.00798571831763024, b = 158.80990662459416, loc = -0.2588341641353391, scale = 32.41213296871982)
        return abs(val)
    
    def TA_factura(self):
        val = logistic.rvs(loc=504.9339, scale=274.9342)/1000
        return abs(val)

    def TA_detalle(self):
        val = lognorm.rvs(s= 0.9810111787531633,  loc= 1.889837813220064, scale= 637.3339586576031)/1000
        return abs(val)

if __name__ == "__main__":
    for i in range(0, 3):
        for j in range(0,3):
            Simulation(i, j, 2500000).exec().print()
