import matplotlib.pyplot as plt
import ast

class Visualizer:
    def __init__(self,
                 pickup_color="#3C6EBD",
                 dropoff_color="#4C9F70",
                 depot_color="#FFA500",      # orange
                 marker_size=700,
                 alpha=0.8,
                 show_grid=True):
        self.pickup_color = pickup_color
        self.dropoff_color = dropoff_color
        self.depot_color = depot_color
        self.marker_size = marker_size
        self.alpha = alpha
        self.show_grid = show_grid

    def _set_plot_bounds(self, ax, xy_range):
        pad = 30

        ax.set_xlim(-10, xy_range + pad)
        ax.set_ylim(-10, xy_range + pad)

    def plot_stops(self, stops, xy_range, ax=None):
        if not stops:
            print("No stops to plot.")
            return None, None

        pu_x, pu_y, pu_ids, pu_labels = [], [], [], []
        do_x, do_y, do_ids, do_labels = [], [], [], []
        dep_x, dep_y, dep_ids, dep_labels = [], [], [], []

        for s in stops:
            t = s.type.upper()
            if t == "PU":
                label = f"{s.name}\n{s.weight:,.0f}lbs"
                pu_x.append(s.x); pu_y.append(s.y); pu_ids.append(s.id); pu_labels.append(label)
            elif t == "DO":
                label = f"{s.name}\n{s.weight:,.0f}lbs"
                do_x.append(s.x); do_y.append(s.y); do_ids.append(s.id); do_labels.append(label)
            elif t in ("DEP", "DEPOT"):
                dep_x.append(s.x); dep_y.append(s.y); dep_ids.append(s.id); dep_labels.append(t)

        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 10))
            created_fig = True
        else:
            fig = ax.figure

        pu_plot = ax.scatter(pu_x, pu_y, s=self.marker_size, color=self.pickup_color,
                             marker="o", label="Pickup (PU)", edgecolors="black", linewidths=1,
                             zorder=2, alpha=self.alpha)
        do_plot = ax.scatter(do_x, do_y, s=self.marker_size, color=self.dropoff_color,
                             marker="o", label="Dropoff (DO)", edgecolors="black", linewidths=1,
                             zorder=2, alpha=self.alpha)
        dep_plot = None
        if dep_x:
            dep_plot = ax.scatter(dep_x, dep_y, s=self.marker_size, color=self.depot_color,
                                  marker="o", label="Depot / Origin", edgecolors="black", linewidths=1,
                                  zorder=2.5, alpha=self.alpha)

        def label_points(x_list, y_list, id_list):
            for x, y, id_ in zip(x_list, y_list, id_list):
                ax.text(x, y, str(id_), color="white", ha="center", va="center", fontsize=7, fontweight="bold", zorder=3)

        label_points(pu_x,  pu_y,  pu_ids)
        label_points(do_x,  do_y,  do_ids)
        label_points(dep_x, dep_y, dep_ids)

        for x, y, label in zip(
            pu_x + do_x + dep_x,
            pu_y + do_y + dep_y,
            pu_labels + do_labels + dep_labels,
        ):
            ax.annotate(
                label,
                xy=(x, y),
                xytext=(16, 0),          # fixed visual offset from marker
                textcoords="offset points",
                color="#232323",
                fontsize=12,
                fontweight="bold",
                ha="left",
                va="center",
                zorder=3,
            )

        ax.set_title("Stop Coordinate Map (PU, DO, & DEPOT)", fontsize=14, fontweight="bold")
        ax.set_xlabel("X Coordinate"); ax.set_ylabel("Y Coordinate")
        if self.show_grid:
            ax.grid(True, linestyle="--", alpha=0.3)

        handles = [pu_plot, do_plot] + ([dep_plot] if dep_plot else [])
        ax.legend(handles=handles, scatterpoints=1, markerscale=0.4, fontsize=12, loc="best", frameon=True)

        self._set_plot_bounds(ax, xy_range)

        if created_fig:
            fig.tight_layout()
            fig.savefig("images/stop_map.png", dpi=300, bbox_inches="tight")
            plt.show()

        return fig, ax

    def plot_route(self, stops, xy_range, ax=None, draw_points=True):
        if not stops or len(stops) < 2:
            print("Need at least 2 stops to draw a route.")
            return None, None

        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 10))
            created_fig = True
        else:
            fig = ax.figure

        # Optionally draw the points on the same ax
        if draw_points:
            _, _ = self.plot_stops(stops, xy_range, ax=ax)

        for i in range(len(stops) - 1):
            s1, s2 = stops[i], stops[i + 1]
            ax.annotate("",
                        xy=(s2.x, s2.y),
                        xytext=(s1.x, s1.y),
                        arrowprops=dict(
                            arrowstyle="fancy,head_length=2,head_width=1.2,tail_width=1.5",
                            color="#FFA50064",
                            lw=1.0,
                            shrinkA=25,
                            shrinkB=25
                        ))
        self._set_plot_bounds(ax, xy_range)

        if created_fig:
            fig.tight_layout()
            fig.savefig("images/route_map.png", dpi=300, bbox_inches="tight")
            plt.show()

        return fig, ax
    
    def plot_route_by_index(self, depot, stops, route_indexes, xy_range, ax=None, draw_points=True):
        if route_indexes is None:
            print("No route indexes provided.")
            return None, None
        
        if isinstance(route_indexes, str):
            route_indexes = ast.literal_eval(route_indexes)

        # Ensure route starts at depot
        if not route_indexes or route_indexes[0] != 0:
            route_indexes = [0] + route_indexes

        # Build lookup: 0 = depot, 1..n = stops[0..n-1]
        lookup = {0: depot}
        for i, stop in enumerate(stops, start=1):
            lookup[i] = stop

        try:
            route_nodes = [lookup[idx] for idx in route_indexes]
        except KeyError as e:
            print(f"Route index {e} not found in depot/stops lookup.")
            return None, None

        return self.plot_route(route_nodes, ax=ax, xy_range=xy_range, draw_points=draw_points)
