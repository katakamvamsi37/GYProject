import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { money } from '../../utils/format';
export default function SpendingChart({ data }) {
  return (
    <div
      className="spending-chart"
      role="img"
      aria-label="Monthly approved expenses; exact values are listed below"
    >
      <ResponsiveContainer width="100%" height={245}>
        <AreaChart
          data={data.map((item) => ({ ...item, amount: Number(item.amount) }))}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="spend-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ca6d42" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#ca6d42" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="4 5" vertical={false} stroke="#eceae4" />
          <XAxis
            dataKey="month"
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#8a8881', fontSize: 11 }}
            dy={8}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#8a8881', fontSize: 11 }}
            tickFormatter={(value) => (value >= 1000 ? `₹${value / 1000}k` : value)}
            width={60}
          />
          <Tooltip formatter={(value) => money(value)} />
          <Area
            isAnimationActive={false}
            type="monotone"
            dataKey="amount"
            name="Approved expenses"
            stroke="#c36238"
            strokeWidth={2.5}
            fill="url(#spend-gradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
      <details className="chart-data">
        <summary>View monthly amounts</summary>
        <dl>
          {data.map((item) => (
            <div key={item.month}>
              <dt>{item.month}</dt>
              <dd>{money(item.amount)}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}
