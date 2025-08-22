# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, add_days
from hrms.hr.doctype.department_approver.department_approver import get_approvers

def get_department_approvers(employee, leave_type=None):
	"""Get all department approvers for an employee"""
	if not employee:
		return []
	
	employee_doc = frappe.get_doc("Employee", employee)
	department = employee_doc.department
	
	if not department:
		return []
	
	# Get department approvers
	approvers = get_approvers("Department", department)
	return [approver.get("approver") for approver in approvers if approver.get("approver")]

def get_all_required_approvers(employee, leave_type=None):
	"""Get all required approvers for leave application"""
	approvers = []
	
	# Get department approvers
	dept_approvers = get_department_approvers(employee, leave_type)
	approvers.extend(dept_approvers)
	
	# Get leave approver from employee master
	employee_doc = frappe.get_doc("Employee", employee)
	if employee_doc.leave_approver:
		approvers.append(employee_doc.leave_approver)
	
	# Remove duplicates while preserving order
	seen = set()
	unique_approvers = []
	for approver in approvers:
		if approver not in seen:
			seen.add(approver)
			unique_approvers.append(approver)
	
	return unique_approvers

def get_approved_by(leave_application_name):
	"""Get list of users who have approved this leave application"""
	leave_app = frappe.get_doc("Leave Application", leave_application_name)
	
	approved_by = []
	if hasattr(leave_app, 'approval_logs') and leave_app.approval_logs:
		for log in leave_app.approval_logs:
			if log.status == "Approved":
				approved_by.append(log.approver)
	
	return approved_by

def add_approval_log(leave_application_name, approver, status, comments=None):
	"""Add approval log entry"""
	leave_app = frappe.get_doc("Leave Application", leave_application_name)
	
	# Initialize approval_logs if it doesn't exist
	if not hasattr(leave_app, 'approval_logs'):
		leave_app.approval_logs = []
	
	# Add new log entry
	log_entry = {
		"approver": approver,
		"status": status,
		"timestamp": frappe.utils.now(),
		"comments": comments or ""
	}
	
	leave_app.append("approval_logs", log_entry)
	leave_app.save(ignore_permissions=True)
	
	return log_entry

def validate_multi_approver_before_submit(doc, method):
	"""Validate multi-level approval before submitting leave application"""
	# Check if multi-level approval is enabled
	hr_settings = frappe.get_single("HR Settings")
	if not getattr(hr_settings, 'enable_multi_level_approvals', False):
		return
	
	# Get all required approvers
	required_approvers = get_all_required_approvers(doc.employee, doc.leave_type)
	
	if not required_approvers:
		return
	
	# Get approved by list
	approved_by = get_approved_by(doc.name)
	
	# Check if all required approvers have approved
	pending_approvers = [approver for approver in required_approvers if approver not in approved_by]
	
	if pending_approvers:
		frappe.throw(_("Leave application requires approval from: {0}").format(", ".join(pending_approvers)))

@frappe.whitelist()
def approve_leave(leave_application_name, comments=None):
	"""Approve leave application"""
	current_user = frappe.session.user
	
	# Get leave application
	leave_app = frappe.get_doc("Leave Application", leave_application_name)
	
	# Check if user is authorized to approve
	required_approvers = get_all_required_approvers(leave_app.employee, leave_app.leave_type)
	
	if current_user not in required_approvers:
		frappe.throw(_("You are not authorized to approve this leave application"))
	
	# Check if already approved by this user
	approved_by = get_approved_by(leave_application_name)
	if current_user in approved_by:
		frappe.throw(_("You have already approved this leave application"))
	
	# Add approval log
	add_approval_log(leave_application_name, current_user, "Approved", comments)
	
	# Check if all approvals are complete
	approved_by = get_approved_by(leave_application_name)
	pending_approvers = [approver for approver in required_approvers if approver not in approved_by]
	
	if not pending_approvers:
		# All approvals complete, update status
		leave_app.status = "Approved"
		leave_app.save(ignore_permissions=True)
	
	frappe.msgprint(_("Leave application approved successfully"))
	return {"status": "success", "message": "Leave application approved"}

@frappe.whitelist()
def reject_leave(leave_application_name, comments=None):
	"""Reject leave application"""
	current_user = frappe.session.user
	
	# Get leave application
	leave_app = frappe.get_doc("Leave Application", leave_application_name)
	
	# Check if user is authorized to reject
	required_approvers = get_all_required_approvers(leave_app.employee, leave_app.leave_type)
	
	if current_user not in required_approvers:
		frappe.throw(_("You are not authorized to reject this leave application"))
	
	# Add rejection log
	add_approval_log(leave_application_name, current_user, "Rejected", comments)
	
	# Update status
	leave_app.status = "Rejected"
	leave_app.save(ignore_permissions=True)
	
	frappe.msgprint(_("Leave application rejected"))
	return {"status": "success", "message": "Leave application rejected"}