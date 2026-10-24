import QtQuick
import QtGraphs

Rectangle {
    id: root

    width: 700
    height: 350
    color: "#292D5E"

    property var weekCategories: [
        "Week 1",
        "Week 2",
        "Week 3",
        "Week 4"
    ]

    property var weekValues: [0, 0, 0, 0]
    property int yAxisMax: 7

    function cleanValues() {
        var result = []

        for (var i = 0; i < 4; i++) {
            if (!weekValues || weekValues.length <= i) {
                result.push(0)
            } else {
                result.push(Math.round(Number(weekValues[i]) || 0))
            }
        }

        return result
    }

    GraphsView {
        anchors.fill: parent

        theme: GraphsTheme {
            theme: GraphsTheme.Theme.UserDefined
            colorScheme: GraphsTheme.ColorScheme.Dark

            backgroundVisible: true
            backgroundColor: "#292D5E"

            plotAreaBackgroundVisible: true
            plotAreaBackgroundColor: "#292D5E"

            labelTextColor: "#C7C7C7"
            labelBackgroundVisible: false
            labelBorderVisible: false

            gridVisible: true
            grid.mainColor: "#242858"
            grid.subColor: "#242858"

            axisX.mainColor: "#8F91A8"
            axisX.subColor: "#8F91A8"
            axisX.labelTextColor: "#C7C7C7"

            axisY.mainColor: "#8F91A8"
            axisY.subColor: "#8F91A8"
            axisY.labelTextColor: "#C7C7C7"
        }

        BarSeries {
            axisX: BarCategoryAxis {
                categories: root.weekCategories
            }

            axisY: ValueAxis {
                min: 0
                max: root.yAxisMax

                tickAnchor: 0
                tickInterval: 1
                subTickCount: 0

                labelDecimals: 0
                labelFormat: "%.0f"
            }

            BarSet {
                label: "Workout Days"
                values: root.cleanValues()

                color: "#CFF8E5"
                borderColor: "#E5FFF3"
                borderWidth: 1
            }
        }
    }
}