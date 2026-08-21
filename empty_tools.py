# Empty Tools
# Copyright (C) 2026 VGmove
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
	"name" : "Empty Tools",
	"description" : "A set of tools for working with empty objects.",
	"author" : "VGmove",
	"version" : (1, 0, 3),
	"blender" : (5, 0, 0),
	"location" : "View3D > Sidebar > Empty Tools",
	"category" : "Object"
}

import bpy
from mathutils import Matrix
from bpy.types import (Panel,
					   Operator,
					   PropertyGroup,
					   )

from bpy.props import (StringProperty,
					   BoolProperty,
					   IntProperty,
					   FloatProperty,
					   EnumProperty,
					   PointerProperty,
					   FloatVectorProperty,
					   )

# Handlers Properties
class EmptyTools_handlers:
	@staticmethod
	def update_empty_size(self, context):
		empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
		if not empties:
			return
			
		EmptyToolsManager.update_empty_size(empties)

# Scene Properties
class EmptyTools_properties(PropertyGroup):
	blank_hierarchy: BoolProperty(
		name="Blank Hierarchy",
		description="Remove empties that form an empty hierarchy.",
		default = True
	)

	excess_empties: BoolProperty(
		name="Excess Empties",
		description="Remove excess empties that have one child.",
		default = True
	)

	keep_structure: BoolProperty(
		name="Keep Structure",
		description="Preserve empty objects that affect hierarchy structure.",
		default = True
	)

	empty_in_modifiers: BoolProperty(
		name="Used in Modifiers",
		description="Remove empty used in modifiers.",
		default = False
	)

	current_collection: BoolProperty(
		name="Current Collection",
		description="Create new collection in parent collection.",
		default = False
	)

	keep_parent_empty: BoolProperty(
		name="Keep Parent",
		description="Keep parent object in new collection.",
		default = True
	)

	create_empty_mode: EnumProperty(
		name="Mode",
		description="Choose how new empty objects are created.",
		items=(
			('ACTIVE_OBJECT', "Active Object", "Create empty by active object"),
			('GROUPS', "Groups", "Create empties for selected hierarchy groups"),
		),
		default='ACTIVE_OBJECT'
	)

	align_new_empty: BoolProperty(
		name="Align Empty",
		description="Align new empty by local orientation active object.",
		default = True
	)

	name_from_object: BoolProperty(
		name="Name from Object",
		description="Set name for new empty from active object. \nDefault name `Group`.",
		default = True
	)

	empty_group_name: StringProperty(
		name="Name",
		description="Name for new empty objects.",
		default="Group"
	)

	empty_size: FloatProperty(
		name="Empty Size",
		description="Change size selected empty objects. \nIt also affects the size of the new empty",
		min=0.01,
		max=1,
		default=0.1,
		update=EmptyTools_handlers.update_empty_size
	)

#Operators
class EmptyToolsCreateEmpty(Operator):
	bl_idname = "object.emptytools_create"
	bl_label = "Create Empty"
	bl_description = "Create empty by active object or selected hierarchy groups."
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		props = context.scene.property
		if props.create_empty_mode == 'GROUPS':
			return self.create_groups(context)
		return self.create_by_active_object(context)

	def create_by_active_object(self, context):
		active_obj = context.active_object
		if not active_obj:
			return {"FINISHED"}

		original_parent = active_obj.parent
		selected_objects = context.selected_objects

		# Exclude parent hierarchy from selection
		parents_to_exclude = set()
		parent = active_obj.parent
		while parent:
			parents_to_exclude.add(parent)
			parent = parent.parent

		filtered_selected = [
			obj for obj in selected_objects
			if obj not in parents_to_exclude
		]

		# Save original name
		original_name = active_obj.name
		if context.scene.property.name_from_object:
			active_obj.name = original_name + "_"

		# Create Empty
		empty_obj = bpy.data.objects.new("", None)
		empty_obj.empty_display_type = 'PLAIN_AXES'
		empty_obj.empty_display_size = context.scene.property.empty_size

		# Set name
		if context.scene.property.name_from_object:
			empty_obj.name = original_name
		else:
			empty_obj.name = context.scene.property.empty_group_name or "Group"

		# Link to active object's collection
		if active_obj.users_collection:
			active_obj.users_collection[0].objects.link(empty_obj)
		else:
			context.scene.collection.objects.link(empty_obj)

		# Make active
		empty_obj.select_set(True)
		context.view_layer.objects.active = empty_obj

		# Create Matrix for location and rotation based on align_new_empty
		loc, rot, scale = active_obj.matrix_world.decompose()
		if context.scene.property.align_new_empty:
			empty_obj.matrix_world = Matrix.LocRotScale(loc, rot, (1, 1, 1))
		else:
			empty_obj.matrix_world = Matrix.Translation(loc)

		# Find top-level objects (not children of other selected objects)
		top_level_objects = [
			obj for obj in filtered_selected
			if self.is_top_level(obj, filtered_selected)
		]

		# Parent selected objects to empty
		for obj in top_level_objects:
			original_matrix = obj.matrix_world.copy()
			obj.parent = empty_obj
			obj.matrix_world = original_matrix

		# Parent empty to original parent
		if original_parent and original_parent != empty_obj:
			world_matrix = empty_obj.matrix_world.copy()
			empty_obj.parent = original_parent
			empty_obj.matrix_parent_inverse = original_parent.matrix_world.inverted()
			empty_obj.matrix_world = world_matrix
		return {"FINISHED"}

	def create_groups(self, context):
		selected_objects = list(context.selected_objects)
		if not selected_objects:
			return {"FINISHED"}

		# Only selected objects that are not descendants of another selected object
		# participate as group members. This preserves existing selected sub-hierarchies.
		top_level_objects = [
			obj for obj in selected_objects
			if self.is_top_level(obj, selected_objects)
		]
		if not top_level_objects:
			return {"FINISHED"}

		# Split selection into hierarchy groups by current parent.
		groups = {}
		for obj in top_level_objects:
			groups.setdefault(obj.parent, []).append(obj)

		created_empties = []
		for group_parent, objects in groups.items():
			if not objects:
				continue

			# Center of the group from world-space object origins.
			center = sum((obj.matrix_world.translation for obj in objects), objects[0].matrix_world.translation.copy() * 0.0) / len(objects)

			empty_obj = bpy.data.objects.new(context.scene.property.empty_group_name or "Group", None)
			empty_obj.empty_display_type = 'PLAIN_AXES'
			empty_obj.empty_display_size = context.scene.property.empty_size

			# Keep the new empty in the same collection as the grouped objects.
			link_source = objects[0]
			if link_source.users_collection:
				link_source.users_collection[0].objects.link(empty_obj)
			else:
				context.scene.collection.objects.link(empty_obj)

			empty_obj.matrix_world = Matrix.Translation(center)

			# Insert the new empty into the existing hierarchy without changing transforms.
			if group_parent:
				world_matrix = empty_obj.matrix_world.copy()
				empty_obj.parent = group_parent
				empty_obj.matrix_parent_inverse = group_parent.matrix_world.inverted()
				empty_obj.matrix_world = world_matrix

			for obj in objects:
				original_matrix = obj.matrix_world.copy()
				obj.parent = empty_obj
				obj.matrix_world = original_matrix

			created_empties.append(empty_obj)

		# Select created empties and make the last one active.
		for obj in context.selected_objects:
			obj.select_set(False)
		for empty_obj in created_empties:
			empty_obj.select_set(True)
		if created_empties:
			context.view_layer.objects.active = created_empties[-1]

		return {"FINISHED"}

	def is_top_level(self, obj, objects):
		parent = obj.parent
		while parent:
			if parent in objects:
				return False
			parent = parent.parent
		return True

class EmptyToolsConvert(Operator):
	bl_idname = "object.emptytools_convert"
	bl_label = "Convert Empty"
	bl_description = "Convert empty objects to collections."
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		selected_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY']
		selected_empties = sorted(selected_empties, key=self.depth)

		empty_to_collection = {}
		for empty in selected_empties:
			# Get parent collections
			if context.scene.property.current_collection and empty.parent in empty_to_collection:
				parent_collection = empty_to_collection[empty.parent]
			elif context.scene.property.current_collection and empty.users_collection:
				parent_collection = empty.users_collection[0]
			else:
				parent_collection = context.scene.collection

			# Create new collection
			new_collection = bpy.data.collections.new(empty.name)
			parent_collection.children.link(new_collection)
			
			# Get objects
			empty_to_collection[empty] = new_collection
			objects = [empty] + list(empty.children_recursive)

			# Save transform
			world_matrices = {obj: obj.matrix_world.copy() for obj in objects}

			# Clear parent
			if empty.parent:
				empty.parent = None
				empty.matrix_world = world_matrices[empty]

			# Move to new collection
			for obj in objects:
				for c in list(obj.users_collection):
					c.objects.unlink(obj)

				new_collection.objects.link(obj)
				obj.matrix_world = world_matrices[obj]

			# Remove parent empty if not keeping it
			if not context.scene.property.keep_parent_empty:
				children = list(empty.children)
				child_matrices = {child: child.matrix_world.copy() for child in children}

				for child in children:
					child.parent = None

				for child in children:
					child.matrix_world = child_matrices[child]

				bpy.data.objects.remove(empty)

		return {"FINISHED"}
	
	def depth(self, obj):
		d = 0
		while obj.parent:
			d += 1
			obj = obj.parent
		return d

class EmptyToolsRemove(Operator):
	bl_idname = "object.emptytools_remove"
	bl_label = "Remove Empty"
	bl_description = "Remove empty objects with specific conditions."
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		# Check all object with modifiers and use empty
		empty_in_modifiers = set()
		if not context.scene.property.empty_in_modifiers:
			for obj in context.scene.objects:
				for mod in obj.modifiers:
					for prop_name in ["object", "target", "mirror_object", "offset_object", "center_object"]:
						if hasattr(mod, prop_name):
							obj_ref = getattr(mod, prop_name)
							if obj_ref and obj_ref.type == "EMPTY":
								empty_in_modifiers.add(obj_ref)

		changed = True
		while changed:
			changed = False
			remove_queue = []
			
			empties = [obj for obj in context.selected_objects if obj.type == "EMPTY" and obj not in empty_in_modifiers]
			for empty in empties:
				children = empty.children

				# Remove empty hierarchy
				if context.scene.property.blank_hierarchy and not children:
					remove_queue.append(empty)
					changed = True
					continue

				# Remove intermediate empty
				if context.scene.property.excess_empties and len(children) == 1:
					child = children[0]
					if not context.scene.property.keep_structure or child.type != "EMPTY":
						matrix = child.matrix_world.copy()
						child.parent = empty.parent
						child.matrix_world = matrix
						remove_queue.append(empty)
						changed = True
						continue

			if remove_queue:
				bpy.data.batch_remove(remove_queue)

		return {"FINISHED"}

class EmptyToolsManager:
	@staticmethod
	def update_empty_size(empties):
		for obj in empties:
			obj.empty_display_size = bpy.context.scene.property.empty_size

# UI
class EmptyToolsPanel:
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Empty Tools"
	bl_options = {"DEFAULT_CLOSED"}

	@classmethod
	def poll(cls, context):
		return (context.active_object and context.object.mode == "OBJECT")

class EMPTYTOOLS_PT_create_empty(EmptyToolsPanel, Panel):
	bl_label = "Create Empty"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = False
		col.use_property_decorate = False
		props = context.scene.property

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = "RIGHT"
		split.label(text="Mode")
		mode_col = split.column(align=True)
		mode_col.prop_enum(props, "create_empty_mode", "ACTIVE_OBJECT")
		mode_col.prop_enum(props, "create_empty_mode", "GROUPS")

		if props.create_empty_mode == 'ACTIVE_OBJECT':
			row = col.row()
			split = row.split(factor=0.4)
			split.alignment = "RIGHT"
			split.label(text="Option")
			col_right = split.column()
			col_right.use_property_split = False
			col_right.prop(props, "align_new_empty")

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = "RIGHT"
		split.label(text="Name")
		col_right = split.column()
		col_right.use_property_split = False

		if props.create_empty_mode == 'ACTIVE_OBJECT':
			col_right.prop(props, "name_from_object")
			name_row = col_right.row()
			name_row.enabled = not props.name_from_object
			name_row.prop(props, "empty_group_name", text="")
		else:
			col_right.prop(props, "empty_group_name", text="")

		col.operator(EmptyToolsCreateEmpty.bl_idname, icon="EMPTY_AXIS", text="Create")

class EMPTYTOOLS_PT_convert(EmptyToolsPanel, Panel):
	bl_label = "Convert to Collection"

	@classmethod
	def poll(cls, context):
		return (context.active_object and 
				bpy.context.object.mode == "OBJECT" and 
				any(obj.type == 'EMPTY' for obj in context.selected_objects))

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = "RIGHT"
		split.label(text="Options")
		col_right = split.column()
		col_right.use_property_split = False
		col_right.prop(context.scene.property, "current_collection")
		col_right.prop(context.scene.property, "keep_parent_empty")
		col.operator(EmptyToolsConvert.bl_idname, icon="FILE_REFRESH", text="Convert")

class EMPTYTOOLS_PT_remove(EmptyToolsPanel, Panel):
	bl_label = "Remove Empty"

	@classmethod
	def poll(cls, context):
		return (context.active_object and 
				bpy.context.object.mode == "OBJECT" and 
				any(obj.type == 'EMPTY' for obj in context.selected_objects))

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = "RIGHT"
		split.label(text="Remove")
		col_right = split.column()
		col_right.use_property_split = False
		
		col_right.prop(context.scene.property, "blank_hierarchy")
		col_right.prop(context.scene.property, "excess_empties")
		
		row = col_right.row()
		row.enabled = context.scene.property.excess_empties
		row.prop(context.scene.property, "keep_structure")

		col.separator()

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = "RIGHT"
		split.label(text="Options")
		col_right = split.column()
		col_right.use_property_split = False
		col_right.prop(context.scene.property, "empty_in_modifiers")
		
		col.operator(EmptyToolsRemove.bl_idname, icon="TRASH", text="Remove")

class EMPTYTOOLS_PT_parameters(EmptyToolsPanel, Panel):
	bl_label = "Parameters"

	@classmethod
	def poll(cls, context):
		return (context.active_object and 
				bpy.context.object.mode == "OBJECT" and 
				any(obj.type == 'EMPTY' for obj in context.selected_objects))

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = False
		col.use_property_decorate = False
		col.prop(context.scene.property, "empty_size")

classes = (
	EmptyTools_properties,
	EmptyToolsRemove,
	EmptyToolsConvert,
	EmptyToolsCreateEmpty,
	EMPTYTOOLS_PT_create_empty,
	EMPTYTOOLS_PT_convert,
	EMPTYTOOLS_PT_remove,
	EMPTYTOOLS_PT_parameters
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	
	bpy.types.Scene.property = PointerProperty(type = EmptyTools_properties)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	
	del bpy.types.Scene.property

if __name__ == "__main__" :
	register()
