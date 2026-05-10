
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class FitResult:
    """
    Result of linear regression fit.

    Attributes:
        slope_K_per_mm (float): The slope of the fitted line in K/mm.
        intercept_K (float): The intercept of the fitted line in K.
        r2 (float): The coefficient of determination (R^2) indicating the goodness of fit.
    """

    slope_k_per_mm: float
    intercept_k: float
    r2: float


class LmcCalculator:
    """
    Class responsible for calculating Liquid Metal Cooling (LMC) parameters
    based on temperature profiles and process parameters.

    Methods:
        calculate_lmc: Main method to calculate LMC parameters given positions,
        temperatures, withdrawal speed, and optional TL information.
    """

    def __init__(self,
                 withdraw_mm_per_min: float,
                 front_angle_deg: float,
                 tl_c: Optional[float],
                 tl_window_mm: float):
        """
        Initializes the LmcCalculator with process parameters.

        Args:
            withdraw_mm_per_min (float): The withdrawal speed in mm/min.
            front_angle_deg (float): The angle of the liquid metal front in degrees.
            tl_c (Optional[float]): The temperature at the liquidus line (TL) in °C.
            tl_window_mm (float): The size of the window in mm around the TL position to
            select points from.
        """

        self.withdraw_mm_per_min = withdraw_mm_per_min
        self.front_angle_deg = front_angle_deg
        self.tl_c = tl_c
        self.tl_window_mm = tl_window_mm


    def __linear_regression(self, x: List[float], y: List[float]) -> FitResult:
        """
        Performs linear regression on the given x and y data points.

        Args:
            x (List[float]): The independent variable data points (e.g., positions in mm).
            y (List[float]): The dependent variable data points (e.g., temperatures in °C).
            Returns:
                FitResult: The result of the linear regression, including slope, intercept,
                and R^2 value.

        Raises:
            ValueError: If x and y have different lengths or if there are not enough points
            to perform regression.
        """

        if len(x) != len(y):
            raise ValueError("x and y must have the same length.")
        if len(x) < 2:
            raise ValueError("Need at least 2 points for regression.")

        n = len(x)
        x_mean = sum(x) / n
        y_mean = sum(y) / n

        sxx = sum((xi - x_mean) ** 2 for xi in x)
        if sxx == 0:
            raise ValueError("All x positions are identical; cannot fit a slope.")

        sxy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        slope = sxy / sxx
        intercept = y_mean - slope * x_mean

        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        r2 = 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

        return FitResult(slope_k_per_mm=float(slope), intercept_k=float(intercept), r2=float(r2))


    def __pick_points_near_tl(
        self,
        z_mm: List[float],
        t_c: List[float],
        tl_c: float,
        window_mm: float,
    ) -> Tuple[List[float], List[float]]:
        """
        Selects points from the z_mm and t_c lists that are within a specified window around
        the position corresponding to tl_c.
        Args:
            z_mm (List[float]): List of positions in mm.
            t_c (List[float]): List of temperatures in °C corresponding to the positions in
            z_mm.
            tl_c (float): The temperature at the liquidus line (TL) in °C.
            window_mm (float): The size of the window in mm around the TL position to select
            points from.

        Returns:
            Tuple[List[float], List[float]]: Two lists containing the selected positions and
            their corresponding temperatures.

        Raises:
            ValueError: If z_mm and t_c have different lengths or if no points are found
            within the specified window.
        """

        idx = min(range(len(t_c)), key=lambda i: abs(t_c[i] - tl_c))
        z0 = z_mm[idx]
        selected = [(z, t) for z, t in zip(z_mm, t_c) if abs(z - z0) <= window_mm]

        if len(selected) < 2:
            return z_mm, t_c

        z_sel, t_sel = zip(*selected)
        return list(z_sel), list(t_sel)


    def __compute_velocity_cm_per_min(self, withdraw_mm_per_min: float,
                                      front_angle_deg: float) -> float:
        """
        Computes the velocity of the liquid metal front in cm/min based on the withdrawal speed
        and front angle.

        Args:
            withdraw_mm_per_min (float): The withdrawal speed in mm/min.
            front_angle_deg (float): The angle of the liquid metal front in degrees.

        Returns:
            float: The velocity of the liquid metal front in cm/min.
        """

        theta = math.radians(front_angle_deg)
        return (withdraw_mm_per_min / 10.0) * math.cos(theta)


    def calculate_lmc(
        self,
        positions_mm: List[float],
        temperatures_c: List[float],
    ) -> dict:
        """
        Calculates the Liquid Metal Cooling (LMC) parameters based on the given temperature profile
        and process parameters.

        Args:
            positions_mm (List[float]): List of positions in mm where temperatures were measured.
            temperatures_c (List[float]): List of temperatures in °C corresponding to the positions
            in positions_mm.

        Returns:
            dict: A dictionary containing the calculated LMC parameters, including:
                - G_K_per_cm: The temperature gradient in K/cm.
                - R_K_per_min: The cooling rate in K/min.
                - R2: The coefficient of determination for the linear fit.

        Raises:
            ValueError: If positions_mm and temperatures_c have different lengths or if there are
            not enough points to perform regression.
        """

        if len(positions_mm) != len(temperatures_c):
            raise ValueError("positions_mm and temperatures_c must have the same length.")

        z_fit, t_fit = positions_mm, temperatures_c
        if self.tl_c is not None:
            z_fit, t_fit = self.__pick_points_near_tl(positions_mm,
                                                      temperatures_c,
                                                      self.tl_c,
                                                      self.tl_window_mm)

        fit = self.__linear_regression(z_fit, t_fit)

        g_k_per_cm = abs(fit.slope_k_per_mm) * 10.0
        v_cm_per_min = self.__compute_velocity_cm_per_min(self.withdraw_mm_per_min,
                                                          self.front_angle_deg)
        r_k_per_min = g_k_per_cm * v_cm_per_min

        return {
            "G_K_per_cm": g_k_per_cm,
            "R_K_per_min": r_k_per_min,
            "R2": fit.r2,
        }
