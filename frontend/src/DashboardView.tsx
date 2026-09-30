import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Users,
  UserCheck,
  UserX,
  Palmtree,
  Clock,
  TrendingUp,
  RefreshCw,
  AlertCircle,
  Calendar,
  Building2,
  Award,
} from "lucide-react";

interface KpiMetrics {
  total_employees: number;
  present_today: number;
  absent_today: number;
  on_leave_today: number;
  late_today: number;
  total_overtime_hours: number;
}

interface DepartmentAttendance {
  department: string;
  total_employees: number;
  present: number;
  absent: number;
  percentage: number;
}

interface OvertimeLeader {
  name: string;
  department: string;
  overtime_hours: number;
}

interface LateLeader {
  name: string;
  department: string;
  late_count: number;
  total_late_minutes: number;
}

interface LeaveBreakdown {
  type: string;
  count: number;
}

interface RecentLeave {
  id: number;
  employee_name: string;
  department: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  status: string;
  reason: string;
}

interface DashboardData {
  reference_date: string;
  is_fallback_date: boolean;
  month: string;
  kpis: KpiMetrics;
  department_attendance: DepartmentAttendance[];
  overtime_leaders: OvertimeLeader[];
  late_leaders: LateLeader[];
  leave_breakdown: LeaveBreakdown[];
  recent_leaves: RecentLeave[];
}

interface DashboardViewProps {
  token: string;
}

export function DashboardView({ token }: DashboardViewProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchDashboard() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/dashboard/summary", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error(`Failed to load dashboard data (status ${res.status})`);
      }

      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard metrics");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDashboard();
  }, [token]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <RefreshCw className="size-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading HR Analytics...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="size-6" />
          <p className="font-semibold">{error || "No data available"}</p>
        </div>
        <Button variant="outline" onClick={fetchDashboard} className="gap-2">
          <RefreshCw className="size-4" /> Try Again
        </Button>
      </div>
    );
  }

  const { kpis, department_attendance, overtime_leaders, late_leaders, leave_breakdown, recent_leaves } = data;

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto px-4 py-6 w-full">
      {/* ── Subheader & Controls ── */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-muted/40 p-4 rounded-xl border">
        <div className="flex items-center gap-2">
          <Calendar className="size-5 text-muted-foreground" />
          <div>
            <span className="font-semibold text-foreground text-sm">
              Period: {data.month}
            </span>
            <span className="text-xs text-muted-foreground ml-2">
              (Ref Date: <span className="font-mono font-medium">{data.reference_date}</span>
              {data.is_fallback_date ? " - Latest Records" : " - Today"})
            </span>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchDashboard}
          className="gap-2 shrink-0 bg-background"
        >
          <RefreshCw className="size-3.5" />
          Refresh Stats
        </Button>
      </div>

      {/* ── Top Row: KPI Cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Total Employees */}
        <Card className="shadow-xs hover:border-primary/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Total Staff</span>
              <div className="p-1.5 bg-blue-500/10 text-blue-600 rounded-md">
                <Users className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1">{kpis.total_employees}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">Active personnel</p>
          </CardContent>
        </Card>

        {/* Present Today */}
        <Card className="shadow-xs hover:border-emerald-500/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Present</span>
              <div className="p-1.5 bg-emerald-500/10 text-emerald-600 rounded-md">
                <UserCheck className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1 text-emerald-600">{kpis.present_today}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">Checked in today</p>
          </CardContent>
        </Card>

        {/* Absent Today */}
        <Card className="shadow-xs hover:border-rose-500/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Absent</span>
              <div className="p-1.5 bg-rose-500/10 text-rose-600 rounded-md">
                <UserX className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1 text-rose-600">{kpis.absent_today}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">Unplanned absence</p>
          </CardContent>
        </Card>

        {/* On Leave Today */}
        <Card className="shadow-xs hover:border-amber-500/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">On Leave</span>
              <div className="p-1.5 bg-amber-500/10 text-amber-600 rounded-md">
                <Palmtree className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1 text-amber-600">{kpis.on_leave_today}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">Approved time-off</p>
          </CardContent>
        </Card>

        {/* Late Today */}
        <Card className="shadow-xs hover:border-orange-500/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Late Arrivals</span>
              <div className="p-1.5 bg-orange-500/10 text-orange-600 rounded-md">
                <Clock className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1 text-orange-600">{kpis.late_today}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">After start threshold</p>
          </CardContent>
        </Card>

        {/* Total Overtime */}
        <Card className="shadow-xs hover:border-purple-500/50 transition-colors">
          <CardHeader className="p-4 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Month OT</span>
              <div className="p-1.5 bg-purple-500/10 text-purple-600 rounded-md">
                <TrendingUp className="size-4" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold mt-1 text-purple-600">{kpis.total_overtime_hours}h</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-[11px] text-muted-foreground">Total accumulated</p>
          </CardContent>
        </Card>
      </div>

      {/* ── Middle Row: Department Breakdown & Leave Distribution ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Department Attendance (2 Cols) */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Building2 className="size-5 text-primary" />
              <div>
                <CardTitle className="text-base font-semibold">Attendance by Department</CardTitle>
                <CardDescription>Daily presence percentage across organizational units</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {department_attendance.map((dept) => (
              <div key={dept.department} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">{dept.department}</span>
                  <span className="text-muted-foreground">
                    <span className="font-semibold text-foreground">{dept.present}</span> / {dept.total_employees} present ({dept.percentage}%)
                  </span>
                </div>
                {/* Visual Progress Bar */}
                <div className="w-full h-2.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      dept.percentage >= 80
                        ? "bg-emerald-500"
                        : dept.percentage >= 50
                        ? "bg-amber-500"
                        : "bg-rose-500"
                    }`}
                    style={{ width: `${dept.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Leave Type Breakdown (1 Col) */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Palmtree className="size-5 text-amber-600" />
              <div>
                <CardTitle className="text-base font-semibold">Leave Usage</CardTitle>
                <CardDescription>Distribution by leave category</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {leave_breakdown.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">No leave applications recorded.</p>
            ) : (
              leave_breakdown.map((item) => (
                <div
                  key={item.type}
                  className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20"
                >
                  <span className="text-xs font-medium text-foreground">{item.type} Leave</span>
                  <span className="text-xs px-2.5 py-0.5 font-bold rounded-full bg-primary/10 text-primary">
                    {item.count} requests
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Bottom Row: Leaderboards & Recent Applications ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Overtime & Late Analysis */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Award className="size-5 text-purple-600" />
              <div>
                <CardTitle className="text-base font-semibold">Monthly Overtime Leaderboard</CardTitle>
                <CardDescription>Highest overtime contributors for {data.month}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {overtime_leaders.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">No overtime recorded for this period.</p>
            ) : (
              <div className="flex flex-col divide-y text-xs">
                {overtime_leaders.map((leader, idx) => (
                  <div key={leader.name} className="flex items-center justify-between py-2.5">
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-muted-foreground w-4 text-center">
                        #{idx + 1}
                      </span>
                      <div>
                        <p className="font-semibold text-foreground">{leader.name}</p>
                        <p className="text-[11px] text-muted-foreground">{leader.department}</p>
                      </div>
                    </div>
                    <span className="font-mono font-semibold px-2.5 py-1 bg-purple-500/10 text-purple-700 rounded-md">
                      {leader.overtime_hours} hrs
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Leave Requests */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Calendar className="size-5 text-blue-600" />
              <div>
                <CardTitle className="text-base font-semibold">Recent Leave Requests</CardTitle>
                <CardDescription>Latest employee applications and statuses</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {recent_leaves.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">No recent leave applications.</p>
            ) : (
              <div className="flex flex-col divide-y text-xs">
                {recent_leaves.map((leave) => (
                  <div key={leave.id} className="flex items-center justify-between py-2.5">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground">{leave.employee_name}</span>
                        <span className="text-[10px] text-muted-foreground">({leave.leave_type})</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        {leave.from_date} → {leave.to_date}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        leave.status === "Approved"
                          ? "bg-emerald-100 text-emerald-800"
                          : leave.status === "Pending"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-rose-100 text-rose-800"
                      }`}
                    >
                      {leave.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
