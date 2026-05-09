import React from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';

interface TacticalGaugeProps {
    value: number; // 0 to 100
    label: string;
    color?: string;
}

export function TacticalGauge({ value, label, color = '#00ff88' }: TacticalGaugeProps) {
    const chartRef = React.useRef<any>(null);

    const option = {
        series: [
            {
                type: 'gauge',
                startAngle: 180,
                endAngle: 0,
                min: 0,
                max: 100,
                splitNumber: 5,
                radius: '100%',
                center: ['50%', '70%'],
                itemStyle: {
                    color: color,
                    shadowColor: 'rgba(0, 255, 136, 0.5)',
                    shadowBlur: 10
                },
                progress: {
                    show: true,
                    roundCap: true,
                    width: 8
                },
                pointer: {
                    show: false
                },
                axisLine: {
                    roundCap: true,
                    lineStyle: {
                        width: 8,
                        color: [[1, 'rgba(255, 255, 255, 0.1)']]
                    }
                },
                axisTick: {
                    splitNumber: 2,
                    lineStyle: {
                        width: 2,
                        color: '#999'
                    }
                },
                splitLine: {
                    length: 12,
                    lineStyle: {
                        width: 3,
                        color: '#999'
                    }
                },
                axisLabel: {
                    distance: 30,
                    color: '#999',
                    fontSize: 10
                },
                title: {
                    show: true,
                    offsetCenter: [0, '20%'],
                    fontSize: 12,
                    color: '#666',
                    fontWeight: 'bold',
                    fontFamily: 'monospace'
                },
                detail: {
                    valueAnimation: true,
                    offsetCenter: [0, '-20%'],
                    fontSize: 24,
                    fontWeight: 'bolder',
                    formatter: '{value}%',
                    color: '#fff',
                    fontFamily: 'monospace',
                    shadowBlur: 5,
                    shadowColor: color
                },
                data: [
                    {
                        value: value,
                        name: label
                    }
                ]
            }
        ]
    };

    return (
        <div className="w-full h-full min-h-[100px] min-w-[150px]">
            <ReactECharts
                ref={chartRef}
                option={option}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
            />
        </div>
    );
}
