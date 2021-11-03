#import packages

class MbdynAdapter:
	#initialize values
	
	def run(self):
		dt = interface.initialize()
		self.mbdyn.initialize(case=self.mbdyn_prep.name)

		while interface.is_coupling_ongoing():
			if interface.is_action_required(precice.action_write_iteration_checkpoint()):
				interface.mark_action_fulfilled(precice.action_write_iteration_checkpoint())

			self.mbdyn.set_forces(np.vstack(self.force_tensor))
			if self.mbdyn.solve(False):
				self.module_logger.debug('Something went wrong!')
				exit("diverged")
				
			### evaluate OpenFOAM data

			### evaluate preCICE data
			
			if interface.is_write_data_required(dt):
				for i in range(self.patches):
					interface.write_block_vector_data(
						self.write_data_id[i], self.vertex_ids[i], self.write_data[i])
			
			dt = interface.advance(dt)
			self.current_time_step += decimal.Decimal(str(dt))
			if interface.is_action_required(precice.action_read_iteration_checkpoint()):
				exit("MBDyn is not in tight coupling mode!")
			else:
				
				#MBDyn advance
				if self.mbdyn.solve(True):
					exit("diverged")
		interface.finalize()
