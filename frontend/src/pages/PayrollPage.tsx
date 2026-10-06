/**
 * Payroll — admin/hr: monthly salary register (GET /salary, /salary/summary), CSV export, payslips,
 * "Generate payroll" (POST /salary/generate, D-021) and "Mark as paid" (POST /salary/mark-paid, D-036).
 * employee/manager: My payslips (GET /salary/me — own rows only) with printable payslip modal.
 * Views live in `pages/payroll/`.
 */
import { useAuth } from "@/lib/auth";
import { MyPayslips } from "./payroll/MyPayslips";
import { PayrollRegister } from "./payroll/PayrollRegister";

export function PayrollPage() {
  const { role } = useAuth();
  return role === "admin" || role === "hr" ? <PayrollRegister /> : <MyPayslips />;
}
