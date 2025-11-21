import asyncio
from datetime import datetime

import flet as ft

def main(page: ft.Page):
    page.title = "Smart Home Controller + Simulator"
    page.padding = 0
    page.bgcolor = ft.Colors.BLUE_GREY_50

    # 1/ Simple in-memory "database" of smart home devices and logs
    devices = {
        "light1": {"id": "light1", "name": "Living Room Light", "type": "light", "is_on": False},
        "fan1": {"id": "fan1", "name": "Ceiling Fan", "type": "fan", "speed": 0},
        "thermo1": {"id": "thermo1", "name": "Thermostat", "type": "thermostat", "setpoint": 22.0},
        "door1": {"id": "door1", "name": "Front Door Lock", "type": "lock", "locked": True},
    }
    logs = []
    power_history = []  # List of (timestamp, total_power_usage) tuples

    log_table = None
    power_chart = None

    # Helper: publish log
    def publish_log(device_id: str, action: str):
        msg = {
            "type": "log",
            "device_id": device_id,
            "action": action,
            "user": "user",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        page.pubsub.send_all(msg)

    def compute_total_power() -> float:
        total_power = 0.0
        light = devices["light1"]
        fan = devices["fan1"]
        thermo = devices["thermo1"]

        if light["is_on"]:
            total_power += 40.0  # watts
        total_power += fan["speed"] * 20.0  # watts
        if thermo["setpoint"] > 20:
            total_power += 500.0  # heating
        return total_power

    def update_power_chart():
        nonlocal power_chart
        if power_chart is None or power_chart.page is None or not power_history:
            return
        points = [ft.LineChartDataPoint(x, y) for x, y in power_history]
        max_power = max(y for _, y in power_history) if power_history else 100
        power_chart.data_series = [
            ft.LineChartData(data_points=points, stroke_width=2)
        ]
        power_chart.min_x = power_history[0][0]
        power_chart.max_x = power_history[-1][0]
        power_chart.min_y = 0
        power_chart.max_y = max_power + 50
        power_chart.update()

    # pubsub handler
    def handle_message(msg):
        nonlocal log_table, power_chart
        if not isinstance(msg, dict):
            return
        if msg.get("type") == "log":
            logs.append(msg)
            if log_table is not None:
                log_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(msg["timestamp"])),
                        ft.DataCell(ft.Text(msg["device_id"])),
                        ft.DataCell(ft.Text(msg["action"])),
                        ft.DataCell(ft.Text(msg["user"])),
                    ])
                )
                log_table.update()
        elif msg.get("type") == "power_sample":
            t = msg["time"]
            p = msg["total_power"]
            power_history.append((t, p))
            if len(power_history) > 50:
                power_history.pop(0)
            if power_chart is not None:
                update_power_chart()

    page.pubsub.subscribe(handle_message)

    # Background simulator
    async def simulator_task():
        t = 0.0
        while True:
            total_power = compute_total_power()
            page.pubsub.send_all({"type": "power_sample", "time": t, "total_power": total_power})
            t += 1.0
            await asyncio.sleep(2)

    page.run_task(simulator_task)

    # Card factories (fixed ft.Colors usage)
    def create_light_card():
        status_text = ft.Text("Status: OFF", size=16)
        helper_text = ft.Text("Tap to switch the light", size=12, color=ft.Colors.GREY)

        def toggle_light(e):
            light = devices["light1"]
            light["is_on"] = not light["is_on"]
            if light["is_on"]:
                status_text.value = "Status: ON"
                e.control.text = "Turn OFF"
                publish_log(light["id"], "Turned ON")
            else:
                status_text.value = "Status: OFF"
                e.control.text = "Turn ON"
                publish_log(light["id"], "Turned OFF")
            status_text.update()
            e.control.update()

        button = ft.ElevatedButton("Turn ON", on_click=toggle_light)
        details_button = ft.TextButton("Details", on_click=lambda e: page.go("/device/light1"))

        return ft.Container(
            bgcolor=ft.Colors.AMBER_50,
            border_radius=16,
            padding=20,
            width=360,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB, size=30, color=ft.Colors.AMBER),
                            ft.Text("💡 Living Room Light", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    ),
                    status_text,
                    helper_text,
                    ft.Row(controls=[details_button, button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=8,
            ),
        )

    def create_fan_card():
        speed_text = ft.Text("Fan speed: 0")
        helper_text = ft.Text("Adjust the fan speed (0=OFF, 3=MAX)", size=12, color=ft.Colors.GREY)

        def change_speed(e):
            fan = devices["fan1"]
            # slider value might be float - cast safely
            try:
                fan["speed"] = int(round(float(e.control.value)))
            except Exception:
                fan["speed"] = 0
            speed_text.value = f"Fan speed: {fan['speed']}"
            speed_text.update()
            publish_log(fan["id"], f"Speed set to {fan['speed']}")

        slider = ft.Slider(min=0, max=3, divisions=3, value=0, label="{value}", on_change=change_speed)
        details_button = ft.TextButton("Details", on_click=lambda e: page.go("/device/fan1"))

        return ft.Container(
            bgcolor=ft.Colors.BLUE_50,
            border_radius=16,
            padding=20,
            width=360,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.AIR, size=30, color=ft.Colors.BLUE),
                            ft.Text("🌀 Ceiling Fan", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    ),
                    speed_text,
                    helper_text,
                    slider,
                    ft.Row(controls=[details_button], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=8,
            ),
        )

    def create_thermostat_card():
        setpoint_text = ft.Text("Setpoint: 22°C")
        helper_text = ft.Text("Adjust the temperature", size=12, color=ft.Colors.GREY)

        def change_temp(e):
            try:
                val = float(e.control.value)
            except Exception:
                val = devices["thermo1"]["setpoint"]
            devices["thermo1"]["setpoint"] = val
            setpoint_text.value = f"Setpoint: {devices['thermo1']['setpoint']:.1f}°C"
            setpoint_text.update()
            publish_log("thermo1", f"Temperature set to {devices['thermo1']['setpoint']:.1f}°C")

        slider = ft.Slider(min=15, max=30, value=22, divisions=30, label="{value}°C", on_change=change_temp)
        details_button = ft.TextButton("Details", on_click=lambda e: page.go("/device/thermo1"))

        return ft.Container(
            bgcolor=ft.Colors.RED_50,
            border_radius=16,
            padding=20,
            width=360,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DEVICE_THERMOSTAT, size=30, color=ft.Colors.RED),
                            ft.Text("🌡️ Thermostat", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    ),
                    setpoint_text,
                    helper_text,
                    slider,
                    ft.Row(controls=[details_button], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=8,
            ),
        )

    def create_door_card():
        status_text = ft.Text("Door: LOCKED", size=16)
        helper_text = ft.Text("Tap to lock/unlock the door", size=12, color=ft.Colors.GREY)

        def toggle_lock(e):
            lock = devices["door1"]
            lock["locked"] = not lock["locked"]
            if lock["locked"]:
                status_text.value = "Door: LOCKED"
                e.control.text = "Unlock"
                publish_log(lock["id"], "Locked")
            else:
                status_text.value = "Door: UNLOCKED"
                e.control.text = "Lock"
                publish_log(lock["id"], "Unlocked")
            status_text.update()
            e.control.update()

        button = ft.ElevatedButton("Unlock", on_click=toggle_lock)
        details_button = ft.TextButton("Details", on_click=lambda e: page.go("/device/door1"))

        return ft.Container(
            bgcolor=ft.Colors.BROWN_50,
            border_radius=16,
            padding=20,
            width=360,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DOOR_FRONT_DOOR, size=30, color=ft.Colors.BROWN),
                            ft.Text("🚪 Front Door", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    ),
                    status_text,
                    helper_text,
                    ft.Row(controls=[details_button, button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=8,
            ),
        )

    # AppBar builder
    def build_appbar(current_route: str) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Text("Smart Home Controller"),
            center_title=False,
            bgcolor=ft.Colors.WHITE,
            actions=[
                ft.TextButton("Overview", on_click=lambda e: page.go("/overview"),
                              style=ft.ButtonStyle(color=ft.Colors.BLUE if current_route.startswith("/overview") else ft.Colors.BLACK)),
                ft.TextButton("Statistics", on_click=lambda e: page.go("/statistics"),
                              style=ft.ButtonStyle(color=ft.Colors.BLUE if current_route.startswith("/statistics") else ft.Colors.BLACK)),
            ],
        )

    # Routing: simpler string-based approach (more robust)
    def route_change(route):
        nonlocal log_table, power_chart
        page.views.clear()
        r = page.route or "/"

        # Overview
        if r == "/" or r == "" or r == "/overview":
            view = ft.View(
                route="/overview",
                appbar=build_appbar("/overview"),
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("On/Off devices", size=24, weight=ft.FontWeight.BOLD),
                                ft.Row(controls=[create_light_card(), create_door_card()], wrap=True, spacing=20),
                                ft.Divider(),
                                ft.Text("Slider controlled devices", size=24, weight=ft.FontWeight.BOLD),
                                ft.Row(controls=[create_fan_card(), create_thermostat_card()], wrap=True, spacing=20),
                            ],
                            spacing=20,
                        ),
                        padding=20,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                bgcolor=ft.Colors.BLUE_GREY_50,
            )
            page.views.append(view)

        # Device details (route like /device/light1)
        elif r.startswith("/device/"):
            dev_id = r.split("/")[-1]
            dev = devices.get(dev_id)
            if dev is None:
                title = "Unknown Device"
                info_rows = [ft.Text("Device not found.")]
            else:
                title = f"{dev['name']} Details"
                info_rows = [ft.Text(f"ID: {dev['id']}", size=16), ft.Text(f"Type: {dev['type']}", size=16)]
                if dev["type"] == "light":
                    info_rows.append(ft.Text(f"State: {'ON' if dev['is_on'] else 'OFF'}", size=16))
                elif dev["type"] == "fan":
                    info_rows.append(ft.Text(f"Speed: {dev['speed']}", size=16))
                elif dev["type"] == "thermostat":
                    info_rows.append(ft.Text(f"Setpoint: {dev['setpoint']:.1f}°C", size=16))
                elif dev["type"] == "lock":
                    info_rows.append(ft.Text(f"Locked: {'Yes' if dev['locked'] else 'No'}", size=16))

            device_logs = [log for log in logs if log["device_id"] == dev_id]
            log_controls = [ft.Text(f"{log['timestamp']}: {log['action']} by {log['user']}") for log in device_logs]

            view = ft.View(
                route=f"/device/{dev_id}",
                appbar=build_appbar(f"/device/{dev_id}"),
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(title, size=24, weight=ft.FontWeight.BOLD),
                                ft.Column(controls=info_rows, spacing=5),
                                ft.Divider(),
                                ft.Text("Recent actions:", size=20, weight=ft.FontWeight.BOLD),
                                ft.Column(controls=log_controls or [ft.Text("No actions recorded yet.")], spacing=2),
                                ft.ElevatedButton("Back to Overview", on_click=lambda e: page.go("/overview")),
                            ],
                            spacing=15,
                        ),
                        padding=20,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                bgcolor=ft.Colors.BLUE_GREY_50,
            )
            page.views.append(view)

        # Statistics
        elif r == "/statistics":
            log_table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Time")),
                    ft.DataColumn(ft.Text("Device")),
                    ft.DataColumn(ft.Text("Action")),
                    ft.DataColumn(ft.Text("User")),
                ],
                rows=[
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(log["timestamp"])),
                        ft.DataCell(ft.Text(log["device_id"])),
                        ft.DataCell(ft.Text(log["action"])),
                        ft.DataCell(ft.Text(log["user"])),
                    ]) for log in logs
                ],
            )

            power_chart = ft.LineChart(
                data_series=[],
                border=ft.border.all(1, ft.Colors.GREY),
                horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_300, width=0.5),
                vertical_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_300, width=0.5),
                min_x=0, max_x=10, min_y=0, max_y=100,
                tooltip_bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLUE_GREY),
                animate=1000, expand=True,
            )

            view = ft.View(
                route="/statistics",
                appbar=build_appbar("/statistics"),
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Power consumption (simulated)", size=24, weight=ft.FontWeight.BOLD),
                                ft.Container(content=power_chart, height=300, padding=10, border=ft.border.all(1, ft.Colors.GREY_400)),
                                ft.Divider(),
                                ft.Text("Action log", size=24, weight=ft.FontWeight.BOLD),
                                ft.Container(content=log_table, bgcolor=ft.Colors.WHITE, border_radius=12, padding=10),
                            ],
                            spacing=20,
                        ),
                        padding=20,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                bgcolor=ft.Colors.BLUE_GREY_50,
            )
            page.views.append(view)
            update_power_chart()

        page.update()

    def view_pop(view):
        page.views.pop()
        if page.views:
            top_view = page.views[-1]
            page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go("/overview")

if __name__ == "__main__":
    ft.app(target=main)
